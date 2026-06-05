import streamlit as st
import numpy as np
import tensorflow as tf
from PIL import Image
import os
import bcrypt
from datetime import datetime
from database import get_db_connection
from brain import get_openai_client, load_my_model, get_ia_response
from utils import es_correo_valido, generar_hoja_tratamiento
from psycopg2.extras import RealDictCursor

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y RECURSOS
# ==========================================
st.set_page_config(page_title="PetSkin AI - Sistema de Soporte", page_icon="🐶", layout="wide")
if not os.path.exists("img_consultas"): 
    os.makedirs("img_consultas")

# Cargar diseño CSS desde archivo externo
try:
    with open("style.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Archivo style.css no encontrado.")

# Carga de recursos de IA
client = get_openai_client()
model = load_my_model()
class_names = ['Dermatitis', 'Fungal_infections', 'Healthy', 'Hypersensitivity', 'demodicosis', 'ringworm']

# ==========================================
# 2. MÓDULOS DE LA APLICACIÓN (VISTAS)
# ==========================================
def mostrar_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_hero, col_spacing, col_login = st.columns([1.1, 0.15, 1])
    
    with col_hero:
        st.markdown(
            "<div class='hero-container'>"
            "<div class='hero-title'>Inteligencia al<br>cuidado clínico.</div>"
            "<div class='hero-subtitle'>PetSkin AI eleva la dermatología veterinaria. Un asistente de visión artificial de grado clínico diseñado para optimizar diagnósticos y la gestión de pacientes.</div>"
            "<div class='hero-list'>"
            "<div><span class='hero-bullet'>—</span> Diagnósticos precisos mediante IA</div>"
            "<div><span class='hero-bullet'>—</span> Historial clínico integrado</div>"
            "<div><span class='hero-bullet'>—</span> Reportes médicos automatizados en PDF</div>"
            "<div><span class='hero-bullet'>—</span> Orientación experta sobre tratamientos 24/7</div>"
            "</div></div>", unsafe_allow_html=True
        )

    with col_login:
        with st.container(border=True):
            st.markdown("<h3 style='color: #000; font-weight: 700; text-align: center; margin-bottom: 5px;'>PetSkin AI</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: #666; text-align: center; font-size: 0.9rem; margin-bottom: 20px;'>Inicia sesión para acceder a tu panel clínico</p>", unsafe_allow_html=True)
            
            tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Crear Cuenta"])
            
            with tab_login:
                u_log = st.text_input("Usuario", key="u_log", placeholder="Ingresa tu usuario")
                p_log = st.text_input("Contraseña", type="password", key="p_log", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True) 
                if st.button("Autenticarse", use_container_width=True):
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s", (u_log,))
                    user = cur.fetchone()
                    cur.close(); conn.close()
                    
                    if user and bcrypt.checkpw(p_log.encode('utf-8'), user['password_hash'].encode('utf-8')):
                        st.session_state.update({'authenticated': True, 'user_id': user['id'], 'username': user['username'], 'role': user.get('role', 'user')})
                        st.rerun()
                    else: 
                        st.error("Credenciales inválidas. Por favor, inténtalo de nuevo.")

            with tab_registro:
                new_u = st.text_input("Nuevo Usuario", key="u_reg", placeholder="Elige un usuario")
                new_e = st.text_input("Correo Electrónico", key="e_reg", placeholder="nombre@clinica.com")
                new_p = st.text_input("Contraseña", type="password", key="p_reg", placeholder="Crea una contraseña segura")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Crear Cuenta", use_container_width=True):
                    if not es_correo_valido(new_e):
                        st.error("Por favor, ingresa un correo electrónico válido.")
                    else:
                        try:
                            conn = get_db_connection(); cur = conn.cursor()
                            hashed = bcrypt.hashpw(new_p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            cur.execute("INSERT INTO users (username, email, password_hash, role) VALUES (%s,%s,%s,'user')", (new_u, new_e, hashed))
                            conn.commit(); cur.close(); conn.close()
                            st.success("Cuenta creada exitosamente. Ya puedes iniciar sesión.")
                        except:
                            st.error("El usuario o correo ya se encuentran registrados.")

def mostrar_admin():
    st.markdown("<h2 style='margin-bottom: 30px;'>Gestión Administrativa de Usuarios</h2>", unsafe_allow_html=True)
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, email, role FROM users ORDER BY id ASC")
    usuarios = cur.fetchall()

    for usr in usuarios:
        with st.expander(f"👤 ID: {usr['id']} | {usr['username']} ({usr['role']})"):
            col1, col2 = st.columns(2)
            edit_u = col1.text_input("Username", value=usr['username'], key=f"u_{usr['id']}")
            edit_e = col2.text_input("Email", value=usr['email'], key=f"e_{usr['id']}")
            edit_r = st.selectbox("Rol", ["user", "admin"], index=0 if usr['role'] == 'user' else 1, key=f"r_{usr['id']}")
            
            c_act, c_elim = st.columns(2)
            if c_act.button("Actualizar", key=f"upd_{usr['id']}", use_container_width=True):
                cur.execute("UPDATE users SET username=%s, email=%s, role=%s WHERE id=%s", (edit_u, edit_e, edit_r, usr['id']))
                conn.commit(); st.success("Datos actualizados"); st.rerun()
            
            if c_elim.button("Eliminar 🗑️", key=f"del_u_{usr['id']}", use_container_width=True):
                if usr['id'] == st.session_state.user_id:
                    st.error("No puedes eliminarte a ti mismo.")
                else:
                    cur.execute("DELETE FROM users WHERE id=%s", (usr['id'],))
                    conn.commit(); st.warning("Usuario eliminado"); st.rerun()
    cur.close(); conn.close()

def mostrar_panel_clinico():
    if 'current_conv_id' not in st.session_state: st.session_state.current_conv_id = None
    if 'chat_history' not in st.session_state: st.session_state.chat_history = []

    if st.sidebar.button("➕ Nueva Consulta", use_container_width=True):
        st.session_state.current_conv_id = None
        st.session_state.chat_history = []
        st.rerun()

    st.sidebar.markdown("<p style='font-size: 0.9rem; color: #666; margin-top: 20px;'><b>Historial de Consultas</b></p>", unsafe_allow_html=True)
    
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, diagnostico_ml, fecha, imagen_path FROM conversations WHERE user_id = %s ORDER BY fecha DESC", (st.session_state.user_id,))
    for conv in cur.fetchall():
        col_c, col_d = st.sidebar.columns([0.80, 0.20])
        
        # Botón para cargar el historial
        if col_c.button(f"{conv['fecha'].strftime('%d/%m')} - {conv['diagnostico_ml']}", key=f"c_{conv['id']}", use_container_width=True):
            st.session_state.current_conv_id = conv['id']
            cur_int = conn.cursor(cursor_factory=RealDictCursor)
            cur_int.execute("SELECT role, content FROM chat_messages WHERE conversation_id = %s ORDER BY id ASC", (conv['id'],))
            st.session_state.chat_history = cur_int.fetchall(); cur_int.close(); st.rerun()
            
        # SOLUCIÓN: Botón para eliminar asegurando retorno a "Nueva Consulta" si se borra el chat actual
        if col_d.button("🗑️", key=f"del_{conv['id']}", use_container_width=True):
            cur_del = conn.cursor()
            cur_del.execute("DELETE FROM chat_messages WHERE conversation_id = %s", (conv['id'],))
            cur_del.execute("DELETE FROM conversations WHERE id = %s", (conv['id'],))
            conn.commit(); cur_del.close()
            
            if st.session_state.current_conv_id == conv['id']:
                st.session_state.current_conv_id = None
                st.session_state.chat_history = []
            
            st.rerun()
    cur.close(); conn.close()

    st.markdown("<h2 style='margin-bottom: 25px;'>Panel Clínico Especializado</h2>", unsafe_allow_html=True)
    col_foto, col_espacio_mid, col_info = st.columns([1, 0.05, 1.2])

    with col_foto:
        with st.container(border=True):
            st.markdown("<div style='font-size: 1.1rem; font-weight: 700; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 20px;'>📸 Imagen del Paciente</div>", unsafe_allow_html=True)
            if st.session_state.current_conv_id:
                conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT imagen_path FROM conversations WHERE id = %s", (st.session_state.current_conv_id,))
                res = cur.fetchone(); cur.close(); conn.close()
                if res and os.path.exists(res['imagen_path']):
                    st.image(Image.open(res['imagen_path']), caption="Caso actual", use_container_width=True)
            else:
                archivo = st.file_uploader("Sube la fotografía dermatológica", type=["jpg", "jpeg", "png"])
                if archivo:
                    if archivo.size > 20 * 1024 * 1024: st.error("Límite 20MB")
                    else: st.image(Image.open(archivo), caption="Vista previa", use_container_width=True)

    with col_info:
        with st.container(border=True):
            st.markdown("<div style='font-size: 1.1rem; font-weight: 700; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 20px;'>🔬 Análisis y Diagnóstico</div>", unsafe_allow_html=True)
            
            if not st.session_state.current_conv_id and 'archivo' in locals() and archivo is not None:
                with st.spinner("Procesando imagen con IA Clínica..."):
                    img = Image.open(archivo).resize((224, 224))
                    pred = model.predict(tf.expand_dims(tf.keras.utils.img_to_array(img), 0))
                    conf, res_ml = float(100*np.max(pred[0])), class_names[np.argmax(pred[0])]
                    path = f"img_consultas/u{st.session_state.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                    Image.open(archivo).save(path)
                    
                    conn = get_db_connection(); cur = conn.cursor()
                    cur.execute("INSERT INTO conversations (user_id, diagnostico_ml, confianza_ml, imagen_path) VALUES (%s,%s,%s,%s) RETURNING id",
                                (st.session_state.user_id, res_ml, conf, path))
                    st.session_state.current_conv_id = cur.fetchone()[0]
                    conn.commit(); cur.close(); conn.close(); st.rerun()

            if st.session_state.current_conv_id:
                conn = get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT c.*, m.nombre, m.raza, m.peso, m.tamano, m.historial 
                    FROM conversations c LEFT JOIN mascotas m ON c.mascota_id = m.id WHERE c.id = %s
                """, (st.session_state.current_conv_id,))
                c_data = cur.fetchone()
                
                # SOLUCIÓN: Seguro extra para evitar que colapse si por alguna razón extraña la consulta falla
                if c_data:
                    st.info(f"**Diagnóstico Preliminar:** {c_data['diagnostico_ml']} (Confianza: {c_data['confianza_ml']:.2f}%)")
                    
                    cur.execute("SELECT id, nombre FROM mascotas WHERE user_id = %s", (st.session_state.user_id,))
                    mis_mascotas = cur.fetchall()
                    opciones_m = {m['nombre']: m['id'] for m in mis_mascotas}

                    with st.expander("📋 Ficha del Paciente (Mascota)", expanded=not bool(c_data['mascota_id'])):
                        if not c_data['mascota_id']:
                            modo = st.radio("Registro de paciente:", ["Paciente Existente", "Nuevo Paciente"], horizontal=True)
                            if modo == "Paciente Existente" and mis_mascotas:
                                m_sel = st.selectbox("Selecciona un paciente", options=list(opciones_m.keys()))
                                if st.button("Vincular a Consulta"):
                                    cur.execute("UPDATE conversations SET mascota_id = %s WHERE id = %s", (opciones_m[m_sel], st.session_state.current_conv_id))
                                    conn.commit(); st.rerun()
                            elif modo == "Paciente Existente" and not mis_mascotas:
                                st.warning("No hay pacientes registrados. Selecciona 'Nuevo Paciente'.")
                            
                            if modo == "Nuevo Paciente":
                                with st.form("form_nueva_mascota"):
                                    col_m1, col_m2 = st.columns(2)
                                    n_nom, n_raz = col_m1.text_input("Nombre"), col_m2.text_input("Raza")
                                    n_pes, n_tam = col_m1.number_input("Peso (kg)", min_value=0.1), col_m2.selectbox("Tamaño", ["Pequeño", "Mediano", "Grande"])
                                    n_his = st.text_area("Notas Clínicas (Opcional)")
                                    
                                    if st.form_submit_button("Registrar y Vincular"):
                                        conn_ins = get_db_connection(); cur_ins = conn_ins.cursor()
                                        cur_ins.execute("""INSERT INTO mascotas (user_id, nombre, raza, peso, tamano, historial) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                                                    (st.session_state.user_id, n_nom, n_raz, n_pes, n_tam, n_his))
                                        cur_ins.execute("UPDATE conversations SET mascota_id = %s WHERE id = %s", (cur_ins.fetchone()[0], st.session_state.current_conv_id))
                                        conn_ins.commit(); cur_ins.close(); conn_ins.close(); st.rerun()
                        else:
                            st.success(f"🐾 **Paciente Vinculado:** {c_data['nombre']} | {c_data['raza']} | {c_data['peso']}kg")
                            if st.button("Cambiar Paciente"):
                                cur.execute("UPDATE conversations SET mascota_id = NULL WHERE id = %s", (st.session_state.current_conv_id,))
                                conn.commit(); st.rerun()

                    if st.session_state.chat_history and c_data['mascota_id']:
                        primer_msg = next((m['content'] for m in st.session_state.chat_history if m['role'] == 'assistant'), "Sin tratamiento")
                        datos_m = {'nombre': c_data['nombre'], 'raza': c_data['raza'], 'peso': c_data['peso'], 'tamano': c_data['tamano'], 'historial': c_data['historial']}
                        pdf_bytes = generar_hoja_tratamiento(datos_m, c_data['diagnostico_ml'], primer_msg, c_data['imagen_path'])
                        st.download_button("📄 Descargar Reporte Clínico (PDF)", data=pdf_bytes, file_name=f"Reporte_{c_data['nombre']}.pdf", mime="application/pdf", use_container_width=True)

                    st.markdown("<div style='margin-top: 20px; margin-bottom: 10px; font-weight: 600;'>💬 Asistente Experto (Chat)</div>", unsafe_allow_html=True)
                    with st.container(height=350):
                        if not st.session_state.chat_history and c_data['mascota_id']:
                            with st.chat_message("assistant"):
                                st.write(f"He detectado **{c_data['diagnostico_ml']}** en **{c_data['nombre']}**. ¿Deseas indicaciones sobre el tratamiento sugerido?")
                        for m in st.session_state.chat_history:
                            with st.chat_message(m["role"]): st.markdown(m["content"])

                    pmt = st.chat_input("Consulta al asistente experto...")
                    if pmt:
                        if not c_data['mascota_id']: st.warning("Vincula los datos del paciente primero.")
                        else:
                            with st.chat_message("user"): st.markdown(pmt)
                            cur.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (%s,'user',%s)", (st.session_state.current_conv_id, pmt))
                            conn.commit()
                            with st.chat_message("assistant"):
                                with st.spinner("Procesando..."):
                                    try:
                                        instruccion = ("Eres un asistente experto en dermatología veterinaria canina. Orienta sobre el diagnóstico detectado y salud cutánea. PUEDES mencionar tratamientos generales. NO ESTÁ PROHIBIDO dar dosis exactas (pero sugiere contactar un veterinario).")
                                        ans = get_ia_response(client, instruccion, f"Mascota: {c_data['nombre']}, Peso: {c_data['peso']}kg, Diagnóstico: {c_data['diagnostico_ml']}. Pregunta: {pmt}")
                                        cur.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (%s,'assistant',%s)", (st.session_state.current_conv_id, ans))
                                        conn.commit()
                                        st.session_state.chat_history.extend([{"role": "user", "content": pmt}, {"role": "assistant", "content": ans}])
                                        st.markdown(ans)
                                    except Exception: st.error("Error de conexión con la IA")
                                    finally: cur.close(); conn.close()
                            st.rerun()
                else:
                    # En caso de que falle la consulta
                    st.session_state.current_conv_id = None
                    st.rerun()

# ==========================================
# 3. ENRUTADOR PRINCIPAL (FLUJO DE NAVEGACIÓN)
# ==========================================
if 'authenticated' not in st.session_state: 
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    mostrar_login()
else:
    # Sidebar global para usuarios logueados
    st.sidebar.markdown(f"<h3 style='margin-top: 20px;'>👋 Hola, {st.session_state.username}</h3><hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    seleccion = st.sidebar.radio("Navegación", ["🐶 Panel Clínico", "👥 Usuarios"]) if st.session_state.role == 'admin' else "🐶 Panel Clínico"
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    # Renderizado condicional
    if seleccion == "👥 Usuarios":
        mostrar_admin()
    elif seleccion == "🐶 Panel Clínico":
        mostrar_panel_clinico()
        
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()
