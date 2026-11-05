import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image


@pytest.fixture
def image_bytes():
    out = io.BytesIO()
    Image.new('RGB', (320, 240), (151, 112, 78)).save(out, 'JPEG')
    return out.getvalue()


@pytest.fixture
def db(monkeypatch):
    # Never fall back to secrets or a remote database in automated tests.
    if os.environ.get('PETSKIN_TEST_DB') != 'petskin_test':
        pytest.skip('Set PETSKIN_TEST_DB=petskin_test to enable isolated PostgreSQL integration tests.')
    for name, value in {'DB_HOST':'127.0.0.1', 'DB_PORT':os.environ.get('PETSKIN_TEST_PORT','55439'),
                        'DB_NAME':'petskin_test', 'DB_USER':'postgres', 'DB_PASSWORD':''}.items():
        monkeypatch.setenv(name, value)
    import database
    with database.transaction() as cur:
        cur.execute('TRUNCATE users, mascotas, conversations, chat_messages, access_events, admin_events, audit_findings, storage_cleanup RESTART IDENTITY CASCADE')
        cur.execute(Path('migrations/001_mantis.sql').read_text(encoding='utf-8'))
    yield


@pytest.fixture
def accounts(db):
    import services as svc
    from database import transaction
    admin_id = svc.register('adminqa', 'adminqa@example.com', '12345', True)
    uid = svc.register('usuarioqa', 'usuarioqa@example.com', '12345', True)
    other = svc.register('otroqa', 'otroqa@example.com', '12345', True)
    with transaction() as cur:
        cur.execute("UPDATE users SET role='admin' WHERE id=%s", (admin_id,))
    return {'admin':svc.login('adminqa','12345'), 'user':svc.login('usuarioqa','12345'),
            'other':svc.login('otroqa','12345')}


@pytest.fixture
def case(accounts):
    import services as svc
    s = accounts['user']
    p = svc.save_pet(s, dict(nombre='Pequeñita', raza='Mestiza', peso=10, tamano='Pequeño', historial='Picazón', color='Marrón'))
    cid = svc.create_case(s,p,'ringworm',75,'s3://test-bucket/consultas/test.jpg',str(uuid4()),'mock')
    return s, p, cid
