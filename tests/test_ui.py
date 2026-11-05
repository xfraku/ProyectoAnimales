import pytest
from streamlit.testing.v1 import AppTest

import services as svc

pytestmark = pytest.mark.integration


def button(at,label):
    return next(b for b in at.button if b.label==label)


def test_login_registration_feedback(db):
    at=AppTest.from_file('app.py').run(timeout=20)
    assert not at.exception
    at.text_input(key='login_username').set_value('missing')
    at.text_input(key='login_password').set_value('bad')
    button(at,'Iniciar sesión').click().run()
    assert any('Credenciales inválidas' in x.value for x in at.error)
    assert not any(x.label=='Términos y Condiciones' for x in at.expander)
    assert any(x.label=='Leer los Términos y Condiciones' for x in at.expander)


def test_user_and_specialist_views(accounts,case,monkeypatch,image_bytes):
    import storage
    monkeypatch.setattr(storage,'read_image',lambda _:image_bytes)
    at=AppTest.from_file('app.py')
    at.session_state.session=accounts['user']
    at.run(timeout=20)
    assert not at.exception and not at.error
    assert 'Usuarios' not in at.radio(key='page').options
    at.radio(key='page').set_value('Mis mascotas').run()
    assert any('Pequeñita' in e.label for e in at.expander)
    at.radio(key='page').set_value('Historial').run()
    assert any('Tiña' in x.value for x in at.markdown)
    button(at,'Abrir consulta').click().run()
    assert not at.exception and not at.error
    assert any(b.label=='Ver reporte PDF' for b in at.button)
    button(at,'Eliminar esta consulta').click().run()
    assert any('permanentemente' in w.value for w in at.warning)
    button(at,'Cancelar').click().run()
    assert len(svc.cases(accounts['user']))==1
    button(at,'Eliminar esta consulta').click().run()
    button(at,'Confirmar').click().run()
    assert not svc.cases(accounts['user'])


def test_admin_views_and_confirmation(accounts):
    at=AppTest.from_file('app.py')
    at.session_state.session=accounts['admin']
    at.run(timeout=20)
    at.radio(key='page').set_value('Usuarios').run()
    assert len(at.dataframe)==1 and not at.error and not at.exception
    at.button(key='status_'+str(accounts['user']['id'])).click().run()
    button(at,'Cancelar').click().run()
    assert svc.current_user(accounts['user'])
    at.radio(key='page').set_value('Métricas y auditoría').run()
    button(at,'Ver gráfico').click().run()
    assert not at.exception and not at.error
    assert [m.label for m in at.metric]==['Consultas registradas','Valoradas como útiles','Sin valoración']


def test_chat_failure_and_success(case,accounts,monkeypatch,image_bytes):
    import brain,storage
    from settings import AppError
    monkeypatch.setattr(storage,'read_image',lambda _:image_bytes)
    def fail(*args): raise AppError('No fue posible consultar la IA')
    monkeypatch.setattr(brain,'answer',fail)
    u,p,c=case
    at=AppTest.from_file('app.py')
    at.session_state.session=u
    at.session_state.current_case=c
    at.run(timeout=20)
    at.text_area(key=f'question_{c}').set_value('Tiene dolor intenso')
    button(at,'Enviar consulta').click().run()
    assert any('No fue posible' in x.value for x in at.error)
    assert svc.detail(u,c)[1]==[]
    monkeypatch.setattr(brain,'answer',lambda *a:dict(respuesta='Acude a un veterinario.',urgente=True,motivo_urgencia='Dolor intenso'))
    button(at,'Enviar consulta').click().run()
    assert len(svc.detail(u,c)[1])==2
    assert any('Atención veterinaria' in e.value for e in at.error)
    assert at.text_area(key=f'question_{c}').value==''
    assert not at.exception


def test_specialist_ui_and_revoked_session(accounts):
    a,u=accounts['admin'],accounts['user']
    svc.change_user(a,u['id'],'edit',username='vetqa',email='vetqa@example.com',role='especialista')
    at=AppTest.from_file('app.py')
    at.session_state.session=svc.login('vetqa','12345')
    at.run(timeout=20)
    assert 'Usuarios' not in at.radio(key='page').options
    assert any(x.value=='Especialista' for x in at.caption)
    svc.change_user(a,u['id'],'disable')
    at.radio(key='page').set_value('Mis mascotas').run()
    assert any(b.label=='Iniciar sesión' for b in at.button)
    assert not at.exception
