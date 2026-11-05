"""Authorization and transactions are enforced here, independently of the UI."""
import json
from datetime import datetime, timezone

import bcrypt

from database import transaction
from domain import (INVALID_LOGIN, ROLES, TERMS_VERSION, THRESHOLD, diagnosis, email_address,
                    password_bytes, pet_fields, required_text)
from settings import AccessError, AppError


def authorize(cur, session, admin=False):
    if not session or not session.get('id'):
        raise AccessError('Inicia sesión para continuar.')
    row = cur.execute('SELECT id, username, role, active, session_version, terms_version FROM users WHERE id=%s FOR SHARE',
                      (session['id'],)).fetchone()
    if not row or not row['active'] or row['session_version'] != session.get('session_version'):
        raise AccessError('Tu sesión ha finalizado o tu acceso cambió. Inicia sesión nuevamente.')
    if admin and row['role'] != 'admin':
        raise AccessError('Esta opción está disponible únicamente para administradores.')
    return row


def current_user(session):
    with transaction() as cur:
        return authorize(cur, session)


def register(username, email, password, consent):
    username = required_text(username, 'Usuario')
    email = email_address(email)
    raw = password_bytes(password)
    if not consent:
        raise AppError('Debes aceptar los Términos y Condiciones para crear tu cuenta.')
    hashed = bcrypt.hashpw(raw, bcrypt.gensalt()).decode()
    with transaction() as cur:
        return cur.execute('''INSERT INTO users(username,email,password_hash,role,terms_version,terms_accepted_at)
            VALUES (%s,%s,%s,'user',%s,now()) RETURNING id''', (username, email, hashed, TERMS_VERSION)).fetchone()['id']


def login(username, password, ip=None):
    username = str(username or '').strip()[:100]
    try:
        raw = password_bytes(password)
    except AppError:
        raw = b''
    error = INVALID_LOGIN
    session = None
    with transaction() as cur:
        row = cur.execute('SELECT * FROM users WHERE lower(btrim(username))=lower(%s) FOR UPDATE', (username,)).fetchone()
        event = 'invalid_credentials'
        now = datetime.now(timezone.utc)
        if row and not row['active']:
            error = 'Esta cuenta está inhabilitada. Contacta al administrador.'
            event = 'disabled_account'
        elif row and row['locked_until'] and row['locked_until'] > now:
            error = 'Cuenta bloqueada temporalmente. Inténtalo cuando termine el bloqueo de una hora.'
            event = 'locked_account'
        else:
            valid = False
            if row and raw:
                try:
                    valid = bcrypt.checkpw(raw, row['password_hash'].encode())
                except ValueError:
                    valid = False
            if valid:
                cur.execute('UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=%s', (row['id'],))
                session = {key: row[key] for key in ('id', 'username', 'role', 'session_version', 'terms_version')}
                event = 'login_success'
            elif row:
                attempts = (0 if row['locked_until'] and row['locked_until'] <= now else row['failed_attempts']) + 1
                cur.execute('''UPDATE users SET failed_attempts=%s,
                    locked_until=CASE WHEN %s >= 5 THEN now()+interval '1 hour' ELSE NULL END WHERE id=%s''',
                    (attempts, attempts, row['id']))
                if attempts >= 5:
                    error = 'Se alcanzaron 5 intentos fallidos. La cuenta permanecerá bloqueada durante una hora.'
                    event = 'account_locked'
        cur.execute('INSERT INTO access_events(user_id,event,ip_address) VALUES (%s,%s,%s)',
                    (row['id'] if row else None, event, str(ip)[:64] if ip else None))
    # Raise AFTER commit: otherwise failed attempts and the security event would be rolled back.
    if not session:
        raise AppError(error)
    return session


def accept_terms(session):
    with transaction() as cur:
        authorize(cur, session)
        cur.execute('UPDATE users SET terms_version=%s, terms_accepted_at=now() WHERE id=%s', (TERMS_VERSION, session['id']))


def list_users(session, search=''):
    # Literal substring: '%' and '_' must not behave as wildcard searches.
    pattern = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    with transaction() as cur:
        authorize(cur, session, admin=True)
        return cur.execute('''SELECT id,username,email,role,active,failed_attempts,locked_until FROM users
            WHERE username ILIKE %s OR email ILIKE %s ORDER BY id DESC''', (pattern, pattern)).fetchall()


def change_user(session, target, action, *, username='', email='', role='', password=''):
    if action == 'edit':
        username, email = required_text(username, 'Usuario'), email_address(email)
        if role not in ROLES:
            raise AppError('Selecciona un rol válido.')
    hashed = bcrypt.hashpw(password_bytes(password), bcrypt.gensalt()).decode() if action == 'password' else None
    if action not in ('edit', 'password', 'disable', 'enable', 'delete', 'unlock'):
        raise AppError('Acción no válida.')
    with transaction() as cur:
        # Serialize admin membership changes to protect the last active admin.
        cur.execute('SELECT pg_advisory_xact_lock(784521002)')
        authorize(cur, session, admin=True)
        row = cur.execute('SELECT id,role,active FROM users WHERE id=%s FOR UPDATE', (target,)).fetchone()
        if not row:
            raise AppError('La cuenta ya no existe.')
        if target == session['id'] and action in ('disable', 'delete'):
            raise AppError('No puedes inhabilitar ni eliminar tu propia cuenta.')
        removes_admin = action in ('disable', 'delete') or (action == 'edit' and role != 'admin')
        if row['role'] == 'admin' and row['active'] and removes_admin:
            count = cur.execute("SELECT count(*) AS n FROM users WHERE role='admin' AND active").fetchone()['n']
            if count <= 1:
                raise AppError('Debe permanecer al menos un administrador activo.')
        if action == 'delete':
            for ref in cur.execute('''SELECT imagen_path FROM conversations WHERE user_id=%s
                    UNION SELECT imagen_path FROM mascotas WHERE user_id=%s''', (target, target)).fetchall():
                queue_cleanup(cur, ref['imagen_path'])
            cur.execute('DELETE FROM users WHERE id=%s', (target,))
        elif action == 'edit':
            cur.execute('UPDATE users SET username=%s,email=%s,role=%s,session_version=session_version+1 WHERE id=%s',
                        (username, email, role, target))
        elif action == 'password':
            cur.execute('''UPDATE users SET password_hash=%s,failed_attempts=0,locked_until=NULL,
                session_version=session_version+1 WHERE id=%s''', (hashed, target))
        elif action == 'unlock':
            cur.execute('UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=%s', (target,))
        else:
            cur.execute('UPDATE users SET active=%s,session_version=session_version+1 WHERE id=%s', (action == 'enable', target))
        cur.execute('INSERT INTO admin_events(actor_id,target_id,action) VALUES (%s,%s,%s)', (session['id'], target, action))


def pets(session):
    with transaction() as cur:
        authorize(cur, session)
        return cur.execute('SELECT * FROM mascotas WHERE user_id=%s ORDER BY id DESC', (session['id'],)).fetchall()


def save_pet(session, fields, pet_id=None, image_ref=None):
    fields = pet_fields(**fields)
    with transaction() as cur:
        authorize(cur, session)
        values = tuple(fields[k] for k in ('nombre', 'raza', 'peso', 'tamano', 'historial', 'color'))
        if pet_id:
            row = cur.execute('''UPDATE mascotas SET nombre=%s,raza=%s,peso=%s,tamano=%s,historial=%s,color=%s
                WHERE id=%s AND user_id=%s RETURNING id''', values + (pet_id, session['id'])).fetchone()
            if not row:
                raise AppError('No se encontró la mascota en tu cuenta.')
            return row['id']
        return cur.execute('''INSERT INTO mascotas(nombre,raza,peso,tamano,historial,color,user_id,imagen_path)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', values + (session['id'], image_ref)).fetchone()['id']


def case_row(cur, session, case_id, lock=False):
    authorize(cur, session)
    row = cur.execute('SELECT * FROM conversations WHERE id=%s AND user_id=%s' + (' FOR UPDATE' if lock else ''),
                      (case_id, session['id'])).fetchone()
    if not row:
        raise AppError('La consulta ya no existe o no pertenece a tu cuenta.')
    return row


def cases(session):
    with transaction() as cur:
        authorize(cur, session)
        return cur.execute('''SELECT c.*,coalesce(c.patient_snapshot->>'nombre',m.nombre,'Sin paciente') AS nombre
          FROM conversations c LEFT JOIN mascotas m ON m.id=c.mascota_id
          WHERE c.user_id=%s ORDER BY c.fecha DESC,c.id DESC''', (session['id'],)).fetchall()


def create_case(session, pet_id, code, confidence, ref, request_id, validator_model, urgent=False, alert=''):
    from domain import CLASSES
    if code not in CLASSES or not 0 <= confidence <= 100:
        raise AppError('El modelo devolvió un resultado no válido.')
    with transaction() as cur:
        authorize(cur, session)
        prior = cur.execute('SELECT id FROM conversations WHERE user_id=%s AND request_id=%s',
                            (session['id'], request_id)).fetchone()
        if prior:
            return prior['id']
        pet = cur.execute('SELECT * FROM mascotas WHERE id=%s AND user_id=%s FOR SHARE', (pet_id, session['id'])).fetchone()
        if not pet:
            raise AppError('Selecciona una mascota de tu cuenta.')
        snapshot = {k: pet[k] for k in ('nombre', 'raza', 'peso', 'tamano', 'historial', 'color')}
        # Validate legacy records before linking them to new consultations.
        snapshot = pet_fields(**snapshot)
        snapshot['origen'] = 'Datos registrados al crear la consulta'
        return cur.execute('''INSERT INTO conversations(user_id,mascota_id,diagnostico_ml,confianza_ml,
            imagen_path,patient_snapshot,request_id,validator_model,urgent,alert_reason) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
            ON CONFLICT (user_id,request_id) DO UPDATE SET request_id=EXCLUDED.request_id RETURNING id''',
            (session['id'], pet_id, code, confidence, ref, json.dumps(snapshot), request_id, validator_model,
             bool(urgent), str(alert)[:1000] if urgent else '')).fetchone()['id']


def attach_legacy_pet(session, case_id, pet_id):
    with transaction() as cur:
        row = case_row(cur, session, case_id, lock=True)
        if row['patient_snapshot'] or row['mascota_id']:
            raise AppError('La ficha de una consulta ya vinculada se conserva como registro histórico.')
        pet = cur.execute('SELECT * FROM mascotas WHERE id=%s AND user_id=%s', (pet_id, session['id'])).fetchone()
        if not pet:
            raise AppError('Selecciona una mascota de tu cuenta.')
        data = pet_fields(**{k: pet[k] for k in ('nombre','raza','peso','tamano','historial','color')})
        data['origen'] = 'Paciente vinculado después de la consulta original'
        cur.execute('UPDATE conversations SET mascota_id=%s,patient_snapshot=%s::jsonb WHERE id=%s',
                    (pet_id, json.dumps(data), case_id))


def detail(session, case_id):
    with transaction() as cur:
        row = case_row(cur, session, case_id)
        messages = cur.execute('SELECT * FROM chat_messages WHERE conversation_id=%s ORDER BY id', (case_id,)).fetchall()
        key = row['diagnostico_ml'] if row['confianza_ml'] >= THRESHOLD else 'inconclusive'
        advice = cur.execute('SELECT content FROM preventive_advice WHERE diagnosis_code=%s', (key,)).fetchone()
        row['advice'] = advice['content'] if advice else ''
        row['label'] = diagnosis(row['diagnostico_ml'], row['confianza_ml'])
        return row, messages


def append_exchange(session, case_id, question, answer, urgent, alert, request_id, expected_last_id):
    question = required_text(question, 'Consulta', 4000)
    answer = str(answer or '').strip()
    if not answer or len(answer) > 20000:
        raise AppError('No se recibió una respuesta válida. Vuelve a intentarlo.')
    with transaction() as cur:
        case_row(cur, session, case_id, lock=True)
        if cur.execute('SELECT id FROM chat_messages WHERE conversation_id=%s AND request_id=%s', (case_id, request_id)).fetchone():
            return
        last = cur.execute('SELECT coalesce(max(id),0) AS id FROM chat_messages WHERE conversation_id=%s', (case_id,)).fetchone()['id']
        if last != expected_last_id:
            raise AppError('La conversación cambió en otra pestaña. Actualiza y envía tu consulta de nuevo.')
        cur.execute("INSERT INTO chat_messages(conversation_id,role,content,request_id) VALUES (%s,'user',%s,%s),(%s,'assistant',%s,%s)",
                    (case_id, question, request_id, case_id, answer, request_id))
        if urgent:
            cur.execute('UPDATE conversations SET urgent=TRUE,alert_reason=%s WHERE id=%s', (str(alert)[:1000], case_id))


def save_summary(session, case_id, summary, expected_last_id):
    if not str(summary).strip() or len(summary) > 20000:
        raise AppError('No se recibió un resumen válido.')
    with transaction() as cur:
        case_row(cur, session, case_id, lock=True)
        last = cur.execute('SELECT coalesce(max(id),0) AS id FROM chat_messages WHERE conversation_id=%s', (case_id,)).fetchone()['id']
        if last != expected_last_id:
            raise AppError('Llegaron nuevos mensajes. Genera nuevamente el resumen para incluirlos.')
        cur.execute('UPDATE conversations SET summary=%s,summary_message_id=%s,summary_at=now() WHERE id=%s',
                    (summary, last, case_id))


def feedback(session, case_id, useful):
    if not isinstance(useful, bool):
        raise AppError('Selecciona una valoración válida.')
    with transaction() as cur:
        case_row(cur, session, case_id)
        cur.execute('UPDATE conversations SET useful=%s WHERE id=%s', (useful, case_id))


def queue_cleanup(cur, ref):
    if ref:
        cur.execute('INSERT INTO storage_cleanup(object_ref) VALUES (%s) ON CONFLICT DO NOTHING', (ref,))


def delete_case(session, case_id):
    with transaction() as cur:
        row = case_row(cur, session, case_id, lock=True)
        queue_cleanup(cur, row['imagen_path'])
        cur.execute('DELETE FROM conversations WHERE id=%s', (case_id,))


def cleanup_storage(session, limit=5):
    from storage import delete_image
    with transaction() as cur:
        authorize(cur, session, admin=True)
        rows = cur.execute('SELECT * FROM storage_cleanup ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED', (limit,)).fetchall()
        done = 0
        for row in rows:
            ref = row['object_ref']
            used = cur.execute('''SELECT 1 AS n FROM conversations WHERE imagen_path=%s
                 UNION ALL SELECT 1 AS n FROM mascotas WHERE imagen_path=%s LIMIT 1''', (ref, ref)).fetchone()
            if used:
                cur.execute('DELETE FROM storage_cleanup WHERE id=%s', (row['id'],))
                continue
            try:
                delete_image(ref)
            except AppError:
                cur.execute("UPDATE storage_cleanup SET attempts=attempts+1,last_error='No se pudo borrar el objeto' WHERE id=%s", (row['id'],))
            else:
                cur.execute('DELETE FROM storage_cleanup WHERE id=%s', (row['id'],))
                done += 1
        return done


def admin_data(session):
    with transaction() as cur:
        authorize(cur, session, admin=True)
        return {
            'cases': cur.execute('''SELECT id,diagnostico_ml,confianza_ml,useful,patient_snapshot,fecha FROM conversations ORDER BY id DESC''').fetchall(),
            'access': cur.execute('SELECT id,user_id,event,ip_address,created_at FROM access_events ORDER BY id DESC LIMIT 200').fetchall(),
            'changes': cur.execute('SELECT * FROM admin_events ORDER BY id DESC LIMIT 100').fetchall(),
            'findings': cur.execute('SELECT * FROM audit_findings ORDER BY id DESC LIMIT 100').fetchall(),
            'advice': cur.execute('SELECT * FROM preventive_advice ORDER BY diagnosis_code').fetchall(),
            'cleanup': cur.execute('SELECT id,attempts,last_error,created_at FROM storage_cleanup ORDER BY id').fetchall(),
        }


def add_finding(session, evidence, recommendation):
    evidence = required_text(evidence, 'Evidencia', 5000)
    recommendation = required_text(recommendation, 'Acción recomendada', 5000)
    with transaction() as cur:
        authorize(cur, session, admin=True)
        cur.execute('INSERT INTO audit_findings(actor_id,evidence,recommendation) VALUES (%s,%s,%s)',
                    (session['id'], evidence, recommendation))


def update_advice(session, code, content):
    content = required_text(content, 'Consejo preventivo', 5000)
    with transaction() as cur:
        authorize(cur, session, admin=True)
        cur.execute('UPDATE preventive_advice SET content=%s,updated_by=%s,updated_at=now() WHERE diagnosis_code=%s',
                    (content, session['id'], code))
