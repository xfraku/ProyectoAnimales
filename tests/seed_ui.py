"""Explicitly reset ONLY the isolated local QA database and seed browser fixtures."""
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if (os.environ.get('PETSKIN_TEST_DB') != 'petskin_test' or os.environ.get('DB_HOST') != '127.0.0.1'
        or os.environ.get('DB_NAME') != 'petskin_test'):
    raise RuntimeError('Refusing to reset any database except the explicitly selected local petskin_test.')

import services as svc
from database import transaction

with transaction() as cur:
    cur.execute('TRUNCATE users,mascotas,conversations,chat_messages,access_events,admin_events,audit_findings,storage_cleanup RESTART IDENTITY CASCADE')
    cur.execute(Path('migrations/001_mantis.sql').read_text(encoding='utf-8'))
for name in ('adminqa','usuarioqa','otroqa'):
    uid=svc.register(name,name+'@example.com','12345',True)
    if name=='adminqa':
        with transaction() as cur:
            cur.execute("UPDATE users SET role='admin' WHERE id=%s",(uid,))
user=svc.login('usuarioqa','12345')
pet=svc.save_pet(user,dict(nombre='Pequeñita',raza='Mestiza',peso=10,tamano='Pequeño',historial='Picazón desde ayer.',color='Marrón'))
for confidence in (75,75,45):
    svc.create_case(user,pet,'ringworm',confidence,'s3://test-bucket/consultas/'+str(uuid4())+'.jpg',str(uuid4()),'mock-ui')
print('Local browser fixtures ready. Never use these sample accounts in production.')
