"""Streamlit views. Services enforce authorization independently of the interface."""
import hashlib
import logging
import uuid
from collections import Counter

import pandas as pd
import streamlit as st

import brain
import services as svc
import storage
from domain import (DISCLAIMER, LABELS, ROLE_LABELS, ROLES, TERMS_VERSION, THRESHOLD,
                    diagnosis, pet_fields, required_text, teams_url, validate_image)
from reports import generate_report
from settings import AccessError, AppError, ROOT, setting

log = logging.getLogger(__name__)
st.set_page_config(page_title='PetSkin AI · Cuidado de tu mascota', page_icon='🐾', layout='wide')
st.markdown('<style>' + (ROOT / 'style.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


def flash(message):
    st.session_state.flash = message
    st.rerun()


def action(fn, *args, **kwargs):
    try:
        return True, fn(*args, **kwargs)
    except AccessError:
        raise
    except AppError as exc:
        st.error(str(exc))
        return False, None


def footer():
    st.divider()
    st.caption('PetSkin AI · Orientación dermatológica canina · ' + DISCLAIMER)
    if st.session_state.get('session'):
        with st.expander('Términos y Condiciones'):
            st.markdown((ROOT / 'TERMS.md').read_text(encoding='utf-8'))


def login_view():
    hero, form = st.columns([1.1, 1], gap='large')
    with hero:
        st.markdown(
            '<section class="hero-container" aria-label="Presentación de PetSkin AI">'
            '<div class="eyebrow">PETSKIN AI / CUIDADO CANINO</div>'
            '<h1 class="hero-title">Inteligencia al<br><span>cuidado clínico.</span></h1>'
            '<p class="hero-subtitle">Un asistente de inteligencia artificial para apoyar '
            'la evaluación de la piel de tu mascota y organizar su información clínica.</p>'
            '<ul class="hero-list">'
            '<li><strong>Orientación preliminar</strong> mediante IA</li>'
            '<li><strong>Historial clínico</strong> integrado</li>'
            '<li><strong>Reportes de consulta</strong> en PDF</li>'
            '<li><strong>Asistente disponible</strong> para tus preguntas</li>'
            '</ul>'
            '<p class="hero-note">La IA ofrece una orientación preliminar. '
            'El diagnóstico corresponde al veterinario.</p></section>',
            unsafe_allow_html=True,
        )
    with form, st.container(border=True):
        st.subheader('Bienvenido a PetSkin')
        sign_in, register = st.tabs(['Iniciar sesión', 'Crear cuenta'])
        with sign_in, st.form('login'):
            username = st.text_input('Usuario', key='login_username', max_chars=100)
            password = st.text_input('Contraseña', type='password', key='login_password')
            if st.form_submit_button('Iniciar sesión', type='primary', use_container_width=True):
                ok, session = action(svc.login, username, password, getattr(st.context, 'ip_address', None))
                if ok:
                    st.session_state.clear()
                    st.session_state.session = session
                    st.rerun()
        with register, st.form('register'):
            username = st.text_input('Nuevo usuario', max_chars=100)
            email = st.text_input('Correo electrónico', max_chars=100)
            password = st.text_input('Nueva contraseña', type='password')
            st.caption('Elige una contraseña larga y exclusiva para esta cuenta.')
            with st.expander('Leer los Términos y Condiciones'):
                st.markdown((ROOT / 'TERMS.md').read_text(encoding='utf-8'))
            consent = st.checkbox('He leído y acepto los Términos y Condiciones disponibles en esta pestaña.')
            if st.form_submit_button('Crear cuenta', type='primary', use_container_width=True):
                ok, _ = action(svc.register, username, email, password, consent)
                if ok:
                    st.success('Cuenta creada exitosamente. Ya puedes iniciar sesión.')


def cached_image(ref):
    # Session-local cache, read only after authorization; cleared at logout.
    cache = st.session_state.setdefault('images', {})
    if ref not in cache:
        if len(cache) >= 12:
            cache.pop(next(iter(cache)))
        cache[ref] = storage.read_image(ref)
    return cache[ref]


def cleanup_failed_upload(ref):
    from database import transaction
    try:
        with transaction() as cur:
            svc.queue_cleanup(cur, ref)
    except AppError:
        try:
            storage.delete_image(ref)
        except AppError:
            log.warning('An uploaded file could not be queued for cleanup.')


def pet_form(session, pet=None, link_case=None):
    pet = pet or {}
    key = f"pet_{pet.get('id', 'new')}_{link_case or 0}"
    with st.form(key, clear_on_submit=not bool(pet)):
        a, b = st.columns(2)
        nombre = a.text_input('Nombre *', value=pet.get('nombre', ''), max_chars=100)
        raza = b.text_input('Raza *', value=pet.get('raza', ''), max_chars=100, help='Puedes indicar Mestizo o Desconocida.')
        peso = a.number_input('Peso (kg) *', min_value=0.1, max_value=120.0,
                             value=min(120.0, max(0.1, float(pet.get('peso', 5)))), step=0.1)
        sizes = ['Pequeño', 'Mediano', 'Grande']
        tamano = b.selectbox('Tamaño *', sizes, index=sizes.index(pet['tamano']) if pet.get('tamano') in sizes else 0)
        color = st.text_input('Color del pelaje (opcional)', value=pet.get('color', ''), max_chars=100)
        notes = st.text_area('Antecedentes y notas (opcional)', value=pet.get('historial') or '', max_chars=5000)
        photo = st.file_uploader('Foto de la mascota (opcional)', type=['jpg', 'jpeg', 'png'], key=key+'_photo') if not pet else None
        st.caption('* Campos obligatorios. Peso permitido: de 0,1 a 120 kg.')
        if st.form_submit_button('Guardar cambios' if pet else 'Registrar mascota', type='primary', use_container_width=True):
            def save():
                fields = pet_fields(nombre, raza, peso, tamano, notes, color)
                ref = None
                if photo:
                    image = validate_image(photo.getvalue(), photo.name)
                    svc.current_user(session)
                    ref = storage.upload_image(image, session['id'], str(uuid.uuid4()), 'mascotas')
                try:
                    pet_id = svc.save_pet(session, fields, pet.get('id'), ref)
                except Exception:
                    if ref:
                        cleanup_failed_upload(ref)
                    raise
                if link_case:
                    svc.attach_legacy_pet(session, link_case, pet_id)
                return pet_id
            ok, _ = action(save)
            if ok:
                flash('Ficha de la mascota guardada.')


def pets_view(session):
    st.title('Mis mascotas')
    st.write('Registra a tus pacientes antes del análisis y mantén sus fichas al día.')
    rows = svc.pets(session)
    with st.expander('Registrar una mascota', expanded=not rows):
        pet_form(session)
    if not rows:
        st.info('Aún no tienes mascotas registradas. Empieza con su nombre y datos básicos.')
    for pet in rows:
        with st.expander(f"{pet['nombre']} · {pet['raza']} · #{pet['id']}"):
            if pet.get('imagen_path'):
                ok, image = action(cached_image, pet['imagen_path'])
                if ok:
                    st.image(image, width=220)
            st.caption('Los cambios se aplican a las próximas consultas. Las anteriores conservan sus datos.')
            pet_form(session, pet)


def new_consultation(session):
    st.title('Nueva consulta')
    st.write('Selecciona al paciente y una fotografía nítida de la zona que quieres consultar.')
    rows = svc.pets(session)
    if not rows:
        st.info('Primero registra a tu mascota. También puedes hacerlo desde «Mis mascotas».')
        pet_form(session)
        return
    lookup = {p['id']: p for p in rows}
    pet_id = st.selectbox('1 · Paciente', options=list(lookup),
                        format_func=lambda i: f"{lookup[i]['nombre']} · {lookup[i]['raza']} · #{i}")
    with st.expander('Registrar otro paciente'):
        pet_form(session)
    source = st.radio('2 · Fotografía', ['Galería', 'Cámara'], horizontal=True)
    left, right = st.columns([1, 1], gap='large')
    with left, st.container(border=True):
        file = (st.file_uploader('Seleccionar imagen JPG o PNG', type=['jpg', 'jpeg', 'png'], key='analysis_upload')
                if source == 'Galería' else st.camera_input('Tomar una fotografía', key='analysis_camera'))
        prepared = None
        if file:
            ok, prepared = action(validate_image, file.getvalue(), file.name)
            if ok:
                st.image(prepared, caption='Vista previa de la fotografía', use_container_width=True)
        st.caption('JPG, JPEG o PNG · Hasta 20 MB · Evita desenfoque, oscuridad y documentos.')
    with right, st.container(border=True):
        st.subheader('3 · Analizar la imagen')
        st.write('Primero comprobaremos que la fotografía sea pertinente. Luego, el modelo estimará una de sus seis categorías.')
        st.caption('Las fotografías se envían a OpenAI para la validación. El resultado es orientativo y puede equivocarse.')
        if st.button('Analizar fotografía', type='primary', use_container_width=True, disabled=prepared is None):
            def analyze():
                svc.current_user(session)
                pet_fields(**{k: lookup[pet_id][k] for k in ('nombre','raza','peso','tamano','historial','color')})
                identity = f'{pet_id}:' + hashlib.sha256(prepared).hexdigest()
                if st.session_state.get('analysis_identity') != identity:
                    st.session_state.analysis_identity = identity
                    st.session_state.analysis_request = str(uuid.uuid4())
                request = st.session_state.analysis_request
                with st.spinner('Comprobando la fotografía y analizando la piel…'):
                    validation = brain.validate_relevance(prepared)
                    code, confidence = brain.predict(prepared)
                    svc.current_user(session)
                    ref = storage.upload_image(prepared, session['id'], request)
                    try:
                        case_id = svc.create_case(session, pet_id, code, confidence, ref, request, validation['model'],
                                                  validation['urgente'], validation['motivo_urgencia'])
                    except Exception:
                        cleanup_failed_upload(ref)
                        raise
                st.session_state.setdefault('images', {})[ref] = prepared
                return case_id
            ok, case_id = action(analyze)
            if ok:
                st.session_state.current_case = case_id
                flash('Análisis guardado. Puedes consultar al asistente o descargar el reporte.')


def teams_button():
    url = teams_url(setting('TEAMS_CONTACT_EMAIL', 'gufa978@gmail.com'), setting('TEAMS_MEETING_URL', ''))
    st.link_button('Llamar veterinario ahora', url, type='primary', use_container_width=True)
    st.caption('Se abrirá Microsoft Teams. La llamada depende de la disponibilidad del veterinario.')


def consultation_view(session, case_id):
    case, messages = svc.detail(session, case_id)
    pet = case.get('patient_snapshot') or {}
    st.title(pet.get('nombre') or 'Consulta sin paciente')
    st.caption(f"Consulta #{case_id} · {case['fecha'].strftime('%d/%m/%Y %H:%M:%S')} · Hora de Lima")
    left, right = st.columns([1, 1.25], gap='large')
    image = None
    with left, st.container(border=True):
        st.subheader('Fotografía del paciente')
        ok, image = action(cached_image, case['imagen_path'])
        if ok:
            st.image(image, use_container_width=True)
        elif st.button('Reintentar cargar imagen'):
            st.rerun()
        if pet:
            st.markdown(f"**Raza:** {pet['raza']}  ·  **Peso:** {pet['peso']} kg  ·  **Tamaño:** {pet['tamano']}")
            with st.expander('Ficha y antecedentes'):
                st.write(pet.get('historial') or 'Sin antecedentes registrados.')
                st.caption(pet.get('origen', 'Datos registrados al crear la consulta'))
        else:
            st.warning('Vincula un paciente para continuar la conversación.')
            options = svc.pets(session)
            if options:
                idx = st.selectbox('Paciente para esta consulta', options=range(len(options)),
                                   format_func=lambda i: f"{options[i]['nombre']} · #{options[i]['id']}")
                if st.button('Vincular paciente'):
                    ok, _ = action(svc.attach_legacy_pet, session, case_id, options[idx]['id'])
                    if ok:
                        flash('Paciente vinculado.')
            with st.expander('Registrar y vincular un paciente'):
                pet_form(session, link_case=case_id)
    with right:
        with st.container(border=True):
            st.subheader('Resultado preliminar')
            (st.warning if case['confianza_ml'] < THRESHOLD else st.info)(case['label'])
            st.metric('Confianza del modelo', f"{case['confianza_ml']:.2f} %")
            st.caption('Umbral de presentación: 60 %. La confianza no equivale a exactitud clínica.')
            if case['confianza_ml'] < THRESHOLD:
                st.write('No hay confianza suficiente para indicar una afección. Prueba una fotografía más clara y consulta al veterinario.')
            if case['diagnostico_ml'] == 'ringworm' and case['confianza_ml'] >= THRESHOLD:
                st.warning('Posible riesgo de contagio: la tiña requiere confirmación veterinaria. Evita compartir cepillos y lávate las manos tras el contacto.')
            if case['urgent']:
                st.error('Atención veterinaria: ' + (case['alert_reason'] or 'Se han informado señales preocupantes.'))
                st.write('Ante una emergencia, acude a un servicio veterinario; no esperes una videollamada.')
            st.markdown('**Cuidados preventivos**')
            st.write(case['advice'])
        with st.container(border=True):
            st.subheader('Tu reporte')
            st.caption('Disponible desde el análisis. Incluye la ficha, el resultado y todos los mensajes registrados.')
            pdf = generate_report(case, messages, image)
            st.download_button('Descargar reporte PDF', pdf, f'PetSkin_consulta_{case_id}.pdf', 'application/pdf',
                               type='primary', use_container_width=True, key=f'pdf_download_{case_id}')
            if st.button('Ver reporte PDF', use_container_width=True):
                st.session_state.preview_case = case_id
            if messages:
                last_id = messages[-1]['id']
                fresh = case.get('summary') and case.get('summary_message_id') == last_id
                st.caption('Resumen actualizado.' if fresh else 'Puedes añadir un resumen. La descarga ya incluye toda la conversación.')
                if st.button('Actualizar resumen del reporte', use_container_width=True):
                    with st.spinner('Preparando el resumen…'):
                        ok, summary = action(brain.summarize, case, messages)
                    if ok:
                        ok, _ = action(svc.save_summary, session, case_id, summary, last_id)
                        if ok:
                            flash('Resumen actualizado y disponible en el PDF.')
    if st.session_state.get('preview_case') == case_id:
        with st.expander('Vista previa del reporte PDF', expanded=True):
            st.pdf(pdf, height=600, key=f'pdf_view_{case_id}')
    st.subheader('Conversa sobre esta consulta')
    st.caption('Describe los síntomas, desde cuándo aparecieron y cualquier cambio reciente.')
    for msg in messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
    if not messages:
        with st.chat_message('assistant'):
            st.write(f"El resultado preliminar es: {case['label']}. ¿Qué has observado en tu mascota?")
    teams_button()
    with st.form(f'chat_{case_id}', clear_on_submit=False):
        question = st.text_area('Tu consulta', max_chars=4000, key=f'question_{case_id}',
                                placeholder='Ejemplo: se rasca desde ayer, ¿qué cuidados generales puedo darle?')
        if st.form_submit_button('Enviar consulta', type='primary', disabled=not bool(pet)):
            def send():
                query = required_text(question, 'Consulta', 4000)
                identity = hashlib.sha256((str(case_id)+str(messages[-1]['id'] if messages else 0)+query).encode()).hexdigest()
                request = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
                with st.spinner('Preparando orientación…'):
                    response = brain.answer(case, messages, query)
                    svc.append_exchange(session, case_id, query, response['respuesta'], response['urgente'],
                                        response['motivo_urgencia'], request, messages[-1]['id'] if messages else 0)
            ok, _ = action(send)
            if ok:
                st.session_state.clear_question = case_id
                flash('Respuesta guardada en la consulta.')
    with st.expander('Valorar la orientación recibida'):
        st.write('¿Esta orientación te resultó útil? Tu valoración no mide la exactitud del diagnóstico.')
        a, b = st.columns(2)
        if a.button('Sí, me resultó útil', use_container_width=True):
            svc.feedback(session, case_id, True)
            flash('Gracias por tu valoración.')
        if b.button('No me resultó útil', use_container_width=True):
            svc.feedback(session, case_id, False)
            flash('Gracias. Tu valoración quedó registrada.')
        if case['useful'] is not None:
            st.caption('Valoración guardada: ' + ('Útil' if case['useful'] else 'No útil'))
    if st.button('Eliminar esta consulta'):
        st.session_state.pending = {'kind': 'case', 'id': case_id, 'label': f"#{case_id} · {pet.get('nombre', 'Sin paciente')}"}


def history_view(session):
    st.title('Historial de consultas')
    rows = svc.cases(session)
    search = st.text_input('Buscar por paciente, resultado o número de consulta')
    if not rows:
        st.info('Todavía no hay consultas. Empieza desde «Nueva consulta».')
    for row in rows:
        label = f"#{row['id']} · {row['nombre']} · {row['fecha'].strftime('%d/%m/%Y %H:%M:%S')} · {diagnosis(row['diagnostico_ml'], row['confianza_ml'])}"
        if search.casefold() not in label.casefold():
            continue
        with st.container(border=True):
            st.markdown('**' + label + '**')
            a, b = st.columns([3, 1])
            if a.button('Abrir consulta', key=f"open_{row['id']}", use_container_width=True):
                st.session_state.current_case = row['id']
                st.session_state.next_page = 'Nueva consulta'
                st.rerun()
            if b.button('Eliminar', key=f"delete_{row['id']}", use_container_width=True):
                st.session_state.pending = {'kind': 'case', 'id': row['id'], 'label': label}


def users_view(session):
    st.title('Gestión de usuarios')
    st.write('Busca cuentas, actualiza sus datos y administra sus permisos.')
    search = st.text_input('Buscar por usuario o correo', placeholder='Nombre de usuario o correo electrónico')
    rows = svc.list_users(session, search)
    table = [{'ID': r['id'], 'Usuario': r['username'], 'Correo': r['email'], 'Rol': ROLE_LABELS[r['role']],
              'Estado': 'Activo' if r['active'] else 'Inhabilitado'} for r in rows]
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
    st.caption('Cuentas más recientes primero. Los especialistas tienen las mismas funciones clínicas que los usuarios.')
    if not rows:
        st.info('No se encontraron cuentas para esa búsqueda.')
    for user in rows:
        uid = user['id']
        with st.expander(f"#{uid} · {user['username']} · {'Activo' if user['active'] else 'Inhabilitado'}"):
            with st.form(f'user_{uid}'):
                a, b = st.columns(2)
                name = a.text_input('Usuario', value=user['username'])
                email = b.text_input('Correo electrónico', value=user['email'])
                role = st.selectbox('Rol', ROLES, index=ROLES.index(user['role']), format_func=ROLE_LABELS.get)
                if st.form_submit_button('Guardar cambios', type='primary'):
                    st.session_state.pending = dict(kind='user', id=uid, label=user['username'], action='edit',
                                                    kwargs=dict(username=name, email=email, role=role))
            with st.form(f'password_{uid}'):
                password = st.text_input('Nueva contraseña', type='password')
                if st.form_submit_button('Cambiar contraseña'):
                    st.session_state.pending = dict(kind='user', id=uid, label=user['username'], action='password',
                                                    kwargs=dict(password=password))
            a, b, c = st.columns(3)
            if a.button('Suspender' if user['active'] else 'Reactivar', key=f'status_{uid}', use_container_width=True):
                st.session_state.pending = dict(kind='user', id=uid, label=user['username'],
                                                action='disable' if user['active'] else 'enable', kwargs={})
            if b.button('Desbloquear acceso', key=f'unlock_{uid}', use_container_width=True, disabled=not user['failed_attempts']):
                st.session_state.pending = dict(kind='user', id=uid, label=user['username'], action='unlock', kwargs={})
            if c.button('Eliminar cuenta', key=f'remove_{uid}', use_container_width=True):
                st.session_state.pending = dict(kind='user', id=uid, label=user['username'], action='delete', kwargs={})
            if user['locked_until']:
                st.caption(f"Bloqueo hasta: {user['locked_until']}")


def admin_view(session):
    st.title('Métricas y auditoría')
    data = svc.admin_data(session)
    stats, audit, advice, security = st.tabs(['Estadísticas', 'Auditoría', 'Consejos preventivos', 'Accesos y archivos'])
    with stats:
        rows = data['cases']
        a, b, c = st.columns(3)
        a.metric('Consultas registradas', len(rows))
        b.metric('Valoradas como útiles', sum(r['useful'] is True for r in rows))
        c.metric('Sin valoración', sum(r['useful'] is None for r in rows))
        st.caption('La utilidad es una valoración del usuario; no constituye validación de exactitud clínica.')
        if st.button('Ver gráfico', type='primary'):
            st.session_state.show_chart = True
        if st.session_state.get('show_chart'):
            counts = Counter(diagnosis(r['diagnostico_ml'], r['confianza_ml']) for r in rows)
            chart = pd.DataFrame({'Categoría': list(LABELS.values())+['Resultado no concluyente']})
            chart['Consultas'] = chart['Categoría'].map(lambda label: counts[label])
            st.bar_chart(chart.set_index('Categoría'), color='#177c70')
            st.dataframe(chart, hide_index=True, use_container_width=True)
    with audit:
        st.subheader('Distribución de los datos')
        st.caption('Estas distribuciones ayudan a revisar la cobertura. Por sí solas no demuestran sesgo ni permiten medir exactitud.')
        audit_rows = [{'Consulta': r['id'], 'Raza': (r['patient_snapshot'] or {}).get('raza') or 'No registrada',
                       'Color': (r['patient_snapshot'] or {}).get('color') or 'No registrado',
                       'Resultado': diagnosis(r['diagnostico_ml'], r['confianza_ml'])} for r in data['cases']]
        df = pd.DataFrame(audit_rows, columns=['Consulta','Raza','Color','Resultado'])
        field = st.selectbox('Agrupar por', ['Raza', 'Color', 'Resultado'])
        if not df.empty:
            st.bar_chart(df.groupby(field).size().rename('Consultas'))
        st.dataframe(df, hide_index=True, use_container_width=True)
        with st.form('finding'):
            evidence = st.text_area('Evidencia u observación', max_chars=5000, help='Incluye los números de consulta relevantes.')
            recommendation = st.text_area('Acción recomendada', max_chars=5000)
            if st.form_submit_button('Registrar observación', type='primary'):
                ok, _ = action(svc.add_finding, session, evidence, recommendation)
                if ok:
                    flash('Observación de auditoría registrada.')
        st.dataframe(pd.DataFrame(data['findings']), hide_index=True, use_container_width=True)
    with advice:
        st.write('Estos consejos aparecen junto al resultado y en el reporte. Deben ser revisados por un veterinario.')
        for item in data['advice']:
            code = item['diagnosis_code']
            with st.form(f'advice_{code}'):
                text = st.text_area(LABELS.get(code, 'Resultado no concluyente'), value=item['content'], max_chars=5000)
                if st.form_submit_button('Guardar consejo'):
                    ok, _ = action(svc.update_advice, session, code, text)
                    if ok:
                        flash('Consejo preventivo actualizado.')
    with security:
        st.subheader('Intentos de acceso recientes')
        st.caption('Últimos 200 eventos. Una IP vacía indica que la plataforma no la proporcionó.')
        st.dataframe(pd.DataFrame(data['access']), hide_index=True, use_container_width=True)
        st.subheader('Cambios administrativos')
        st.dataframe(pd.DataFrame(data['changes']), hide_index=True, use_container_width=True)
        st.subheader('Fotografías pendientes de eliminación')
        st.write(f"{len(data['cleanup'])} archivos en cola. Las consultas eliminadas ya no aparecen en el historial.")
        st.dataframe(pd.DataFrame(data['cleanup']), hide_index=True, use_container_width=True)
        if st.button('Procesar archivos pendientes', disabled=not data['cleanup']):
            ok, count = action(svc.cleanup_storage, session, 20)
            if ok:
                flash(f'Se eliminaron {count} archivos. Los que fallen permanecen en la cola para reintentar.')


@st.dialog('Confirmar operación')
def confirm_pending(session):
    pending = st.session_state.pending
    st.write(pending['label'])
    if pending['kind'] == 'case':
        st.warning('Se eliminarán permanentemente esta consulta y todos sus mensajes. Esta acción no se puede deshacer.')
    elif pending['action'] == 'delete':
        st.warning('Se eliminarán permanentemente la cuenta, sus mascotas y sus consultas. Esta acción no se puede deshacer.')
    elif pending['action'] == 'edit':
        st.write({'Usuario': pending['kwargs']['username'], 'Correo': pending['kwargs']['email'],
                  'Rol': ROLE_LABELS.get(pending['kwargs']['role'])})
        st.info('El usuario deberá iniciar sesión nuevamente para aplicar el cambio.')
    else:
        labels = {'disable':'Inhabilitar la cuenta y cerrar sus sesiones.', 'enable':'Reactivar el acceso de la cuenta.',
                  'password':'Actualizar la contraseña y cerrar las sesiones anteriores.', 'unlock':'Quitar el bloqueo por intentos fallidos.'}
        st.info(labels[pending['action']])
    a, b = st.columns(2)
    if a.button('Cancelar', use_container_width=True):
        del st.session_state.pending
        st.rerun()
    if b.button('Confirmar', type='primary', use_container_width=True):
        if pending['kind'] == 'case':
            ok, _ = action(svc.delete_case, session, pending['id'])
        else:
            ok, _ = action(svc.change_user, session, pending['id'], pending['action'], **pending['kwargs'])
        if ok:
            if pending['kind'] == 'case' and st.session_state.get('current_case') == pending['id']:
                st.session_state.current_case = None
            st.session_state.images = {}
            del st.session_state.pending
            notice = 'Consulta eliminada.' if pending['kind'] == 'case' else {
                'edit':'Datos actualizados.', 'password':'Contraseña actualizada.', 'disable':'Cuenta inhabilitada.',
                'enable':'Cuenta reactivada.', 'delete':'Cuenta eliminada.', 'unlock':'Acceso desbloqueado.'}[pending['action']]
            flash(notice)


def main():
    if 'clear_question' in st.session_state:
        st.session_state[f"question_{st.session_state.pop('clear_question')}"] = ''
    if 'flash' in st.session_state:
        st.success(st.session_state.pop('flash'))
    session = st.session_state.get('session')
    if not session:
        login_view()
        return
    user = svc.current_user(session)
    if user['terms_version'] != TERMS_VERSION:
        st.title('Antes de continuar')
        st.write('Consulta los Términos y Condiciones al pie de la página.')
        consent = st.checkbox('He leído y acepto los Términos y Condiciones.')
        if st.button('Continuar', type='primary', disabled=not consent):
            svc.accept_terms(session)
            st.rerun()
        if st.button('Cerrar sesión'):
            st.session_state.clear()
            st.rerun()
        return
    st.sidebar.markdown('## 🐾 PetSkin AI')
    st.sidebar.write(user['username'])
    st.sidebar.caption(ROLE_LABELS[user['role']])
    if user['role'] == 'especialista':
        st.sidebar.caption('Asistencia para la evaluación veterinaria de tus propios pacientes.')
    options = ['Nueva consulta', 'Mis mascotas', 'Historial']
    if user['role'] == 'admin':
        options += ['Usuarios', 'Métricas y auditoría']
    if st.session_state.get('next_page'):
        st.session_state.page = st.session_state.pop('next_page')
    page = st.sidebar.radio('Navegación', options, key='page')
    if st.sidebar.button('Empezar otra consulta', use_container_width=True):
        st.session_state.current_case = None
        for key in ('analysis_identity', 'analysis_upload', 'analysis_camera'):
            st.session_state.pop(key, None)
        st.session_state.next_page = 'Nueva consulta'
        st.rerun()
    st.sidebar.divider()
    if st.sidebar.button('Cerrar sesión', use_container_width=True):
        st.session_state.clear()
        st.rerun()
    if page == 'Nueva consulta':
        if st.session_state.get('current_case'):
            consultation_view(session, st.session_state.current_case)
        else:
            new_consultation(session)
    elif page == 'Mis mascotas':
        pets_view(session)
    elif page == 'Historial':
        history_view(session)
    elif page == 'Usuarios':
        users_view(session)
    else:
        admin_view(session)
    if st.session_state.get('pending'):
        confirm_pending(session)


try:
    main()
except AccessError as exc:
    st.session_state.clear()
    st.session_state.flash = str(exc)
    st.rerun()
except AppError as exc:
    st.error(str(exc))
    if st.button('Volver a intentar'):
        st.rerun()
except Exception as exc:
    log.error('Unexpected application error: %s', type(exc).__name__)
    st.error('No se pudo completar esta acción. Vuelve a intentarlo. Si el problema continúa, informa al administrador.')
finally:
    footer()
