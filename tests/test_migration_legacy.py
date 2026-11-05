from pathlib import Path

import pytest

import services as svc
from database import transaction

pytestmark=pytest.mark.integration


def test_legacy_snapshot_backfill_and_preserved_login(accounts):
    u=accounts['user']
    p=svc.save_pet(u,dict(nombre='Historia antigua',raza='Mestizo',peso=8,tamano='Mediano'))
    with transaction() as cur:
        cid=cur.execute('''INSERT INTO conversations(user_id,mascota_id,diagnostico_ml,confianza_ml,imagen_path)
            VALUES (%s,%s,'ringworm',45,'https://example.invalid/original.jpg') RETURNING id''',(u['id'],p)).fetchone()['id']
        cur.execute("INSERT INTO chat_messages(conversation_id,role,content) VALUES (%s,'user','Mensaje anterior')",(cid,))
        before=cur.execute('SELECT username,email,password_hash,role FROM users WHERE id=%s',(u['id'],)).fetchone()
        cur.execute(Path('migrations/001_mantis.sql').read_text(encoding='utf-8'))
        after=cur.execute('SELECT username,email,password_hash,role FROM users WHERE id=%s',(u['id'],)).fetchone()
        assert before==after
    row,messages=svc.detail(svc.login('usuarioqa','12345'),cid)
    assert row['patient_snapshot']['origen']=='Datos disponibles al migrar'
    assert row['label']=='Resultado no concluyente'
    assert messages[0]['content']=='Mensaje anterior'
