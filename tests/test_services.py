from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

import services as svc
from database import transaction
from settings import AccessError, AppError

pytestmark = pytest.mark.integration


def test_register_duplicates_and_consent(db):
    uid=svc.register('Luna','luna@example.com','12345',True)
    for name,email in [('luna','other@example.com'),('new',' LUNA@EXAMPLE.COM ')]:
        with pytest.raises(AppError,match='registrado'): svc.register(name,email,'12345',True)
    with pytest.raises(AppError): svc.register('new','new@example.com','12345',False)
    assert svc.login(' luna ','12345')['id']==uid
    with transaction() as cur:
        row=cur.execute('SELECT * FROM users WHERE id=%s',(uid,)).fetchone()
        assert row['password_hash']!='12345' and row['terms_accepted_at']


def test_atomic_duplicate_registration(db):
    def attempt(n):
        try: return svc.register('same'+str(n),'same@example.com','12345',True)
        except AppError: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(attempt,[1,2]))
    assert sum(x is not None for x in result)==1


def test_five_failed_attempts_persist_and_expire(accounts):
    for i in range(5):
        with pytest.raises(AppError) as err: svc.login('usuarioqa','bad','192.0.2.1')
        assert ('5 intentos' in str(err.value)) == (i==4)
    with pytest.raises(AppError,match='bloqueada'): svc.login('usuarioqa','12345')
    with transaction() as cur:
        row=cur.execute('SELECT * FROM users WHERE id=%s',(accounts['user']['id'],)).fetchone()
        assert row['failed_attempts']==5 and row['locked_until']
        assert cur.execute("SELECT count(*) n FROM access_events WHERE ip_address='192.0.2.1'").fetchone()['n']==5
        cur.execute("UPDATE users SET locked_until=now()-interval '1 second' WHERE id=%s",(row['id'],))
    assert svc.login('usuarioqa','12345')
    with transaction() as cur:
        assert cur.execute('SELECT failed_attempts n FROM users WHERE id=%s',(row['id'],)).fetchone()['n']==0


def test_lock_concurrent_attempts(accounts):
    def fail(_):
        with pytest.raises(AppError): svc.login('usuarioqa','bad')
    with ThreadPoolExecutor(max_workers=5) as pool: list(pool.map(fail,range(5)))
    with transaction() as cur:
        assert cur.execute('SELECT failed_attempts n FROM users WHERE id=%s',(accounts['user']['id'],)).fetchone()['n']==5


def test_search_permissions_roles_and_revocation(accounts):
    a,u=accounts['admin'],accounts['user']
    with pytest.raises(AccessError): svc.list_users(u)
    assert len(svc.list_users(a,'USUARIOQA@'))==1
    assert not svc.list_users(a,'%')
    ids=[r['id'] for r in svc.list_users(a)]
    assert ids==sorted(ids,reverse=True)
    svc.change_user(a,u['id'],'edit',username='vetqa',email='vetqa@example.com',role='especialista')
    with pytest.raises(AccessError): svc.current_user(u)
    vet=svc.login('vetqa','12345')
    assert vet['role']=='especialista'
    with pytest.raises(AccessError): svc.admin_data(vet)
    svc.change_user(a,vet['id'],'edit',username='vetqa',email='vetqa@example.com',role='admin')
    assert svc.list_users(svc.login('vetqa','12345'))


def test_suspend_reactivate_reset_delete_last_admin(accounts):
    a,u=accounts['admin'],accounts['user']
    svc.change_user(a,u['id'],'disable')
    with pytest.raises(AppError,match='inhabilitada'): svc.login('usuarioqa','12345')
    with pytest.raises(AccessError): svc.current_user(u)
    svc.change_user(a,u['id'],'enable')
    active=svc.login('usuarioqa','12345')
    svc.change_user(a,u['id'],'password',password='updatedpass')
    with pytest.raises(AccessError): svc.current_user(active)
    with pytest.raises(AppError): svc.login('usuarioqa','12345')
    assert svc.login('usuarioqa','updatedpass')
    with pytest.raises(AppError,match='administrador'): svc.change_user(a,a['id'],'edit',username='adminqa',email='adminqa@example.com',role='user')
    with pytest.raises(AppError): svc.change_user(a,a['id'],'delete')
    svc.change_user(a,u['id'],'delete')
    with pytest.raises(AppError): svc.login('usuarioqa','updatedpass')


def test_patient_validation_snapshot_and_ownership(case,accounts):
    u,p,c=case
    with pytest.raises(AppError): svc.save_pet(u,dict(nombre='',raza='Mestiza',peso=5,tamano='Pequeño'))
    with pytest.raises(AppError): svc.create_case(accounts['other'],p,'Dermatitis',80,'s3://test/x',str(uuid4()),'mock')
    with pytest.raises(AppError): svc.detail(accounts['other'],c)
    with pytest.raises(AppError): svc.delete_case(accounts['other'],c)
    svc.save_pet(u,dict(nombre='Nuevo nombre',raza='Mestiza',peso=8,tamano='Mediano'),p)
    row,_=svc.detail(u,c)
    assert row['patient_snapshot']['nombre']=='Pequeñita'
    assert row['patient_snapshot']['peso']==10


def test_case_idempotency_and_chat_atomicity(case,monkeypatch):
    u,p,c=case
    rid=str(uuid4())
    c1=svc.create_case(u,p,'Dermatitis',50,'s3://test-bucket/consultas/test2.jpg',rid,'mock')
    assert svc.create_case(u,p,'Dermatitis',50,'s3://test-bucket/consultas/test2.jpg',rid,'mock')==c1
    row,m=svc.detail(u,c1)
    assert row['label']=='Resultado no concluyente' and 'confianza' in row['advice']
    rid=str(uuid4())
    svc.append_exchange(u,c,'Tiene dolor','Acude al veterinario.',True,'Dolor intenso',rid,0)
    svc.append_exchange(u,c,'Tiene dolor','Acude al veterinario.',True,'Dolor intenso',rid,0)
    row,m=svc.detail(u,c)
    assert len(m)==2 and row['urgent']
    with pytest.raises(AppError,match='otra pestaña'):
        svc.append_exchange(u,c,'Otro','Respuesta',False,'',str(uuid4()),0)
    assert len(svc.detail(u,c)[1])==2
    svc.save_summary(u,c,'Resumen',m[-1]['id'])
    svc.feedback(u,c,True)
    assert svc.detail(u,c)[0]['useful'] is True
    with pytest.raises(AppError): svc.save_summary(u,c,'Viejo',0)


def test_delete_cleanup_and_admin_audit(case,accounts,monkeypatch):
    u,p,c=case
    svc.append_exchange(u,c,'Pregunta','Respuesta',False,'',str(uuid4()),0)
    svc.delete_case(u,c)
    with transaction() as cur:
        assert cur.execute('SELECT count(*) n FROM chat_messages WHERE conversation_id=%s',(c,)).fetchone()['n']==0
    a=accounts['admin']
    import storage
    def fail(_): raise AppError('temporary')
    monkeypatch.setattr(storage,'delete_image',fail)
    assert svc.cleanup_storage(a)==0
    assert svc.admin_data(a)['cleanup'][0]['attempts']==1
    monkeypatch.setattr(storage,'delete_image',lambda _:None)
    assert svc.cleanup_storage(a)==1
    svc.add_finding(a,'Consulta 1: revisar cobertura\nColor marrón','Recopilar más ejemplos')
    svc.update_advice(a,'ringworm','Consejo actualizado')
    data=svc.admin_data(a)
    assert data['findings'] and not data['cleanup']
    assert next(x['content'] for x in data['advice'] if x['diagnosis_code']=='ringworm')=='Consejo actualizado'


def test_migration_repeatable_preserves_data(case):
    from pathlib import Path
    u,p,c=case
    with transaction() as cur:
        cur.execute(Path('migrations/001_mantis.sql').read_text(encoding='utf-8'))
    assert svc.detail(u,c)[0]['patient_snapshot']['nombre']=='Pequeñita'
    assert svc.login('usuarioqa','12345')
