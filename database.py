"""Small PostgreSQL adapter. No runtime schema changes or embedded passwords."""
import logging
import ssl
from contextlib import contextmanager

import pg8000.dbapi

from settings import AccessError, AppError, ROOT, setting

log = logging.getLogger(__name__)


class DictCursor:
    def __init__(self, connection):
        self.raw = connection.cursor()

    def execute(self, statement, params=None):
        self.raw.execute(statement, params or ())
        return self

    def fetchone(self):
        row = self.raw.fetchone()
        return dict(zip((x[0] for x in self.raw.description), row)) if row is not None else None

    def fetchall(self):
        return [dict(zip((x[0] for x in self.raw.description), row)) for row in self.raw.fetchall()]

    @property
    def rowcount(self):
        return self.raw.rowcount

    def close(self):
        self.raw.close()


def connect():
    host = setting('DB_HOST')
    if not host:
        raise AppError('Falta configurar la conexión a la base de datos en Secrets.')
    if host in ('localhost', '127.0.0.1', '::1'):
        tls = False
    else:
        ca = setting('DB_SSLROOTCERT', str(ROOT / 'certs' / 'us-east-2-bundle.pem'))
        tls = ssl.create_default_context(cafile=ca)
    return pg8000.dbapi.connect(host=host, port=int(setting('DB_PORT', 5432)),
                               database=setting('DB_NAME', 'petskin_db'), user=setting('DB_USER'),
                               password=setting('DB_PASSWORD'), ssl_context=tls, timeout=15)


def sqlstate(exc):
    return exc.args[0].get('C') if exc.args and isinstance(exc.args[0], dict) else None


@contextmanager
def transaction():
    conn = None
    cur = None
    try:
        conn = connect()
        cur = DictCursor(conn)
        cur.execute("SET LOCAL statement_timeout = '20s'")
        yield cur
        conn.commit()
    except AppError:
        if conn:
            conn.rollback()
        raise
    except pg8000.dbapi.Error as exc:
        if conn:
            conn.rollback()
        code = sqlstate(exc)
        log.warning('Database operation failed: sqlstate=%s type=%s', code, type(exc).__name__)
        if code == '23505':
            constraint = exc.args[0].get('n', '')
            if 'email' in constraint:
                raise AppError('El correo electrónico ya se encuentra registrado.') from None
            if 'username' in constraint:
                raise AppError('El nombre de usuario ya se encuentra registrado.') from None
            raise AppError('El usuario o correo ya se encuentran registrados.') from None
        if code in ('42P01', '42703'):
            raise AppError('Falta aplicar la actualización de la base de datos. Consulta la guía de despliegue.') from None
        raise AppError('No se pudo completar la operación en la base de datos. Inténtalo nuevamente.') from None
    except (OSError, ValueError) as exc:
        if conn:
            conn.rollback()
        log.warning('Database connection failed: %s', type(exc).__name__)
        raise AppError('No se pudo conectar a la base de datos. Revisa la conexión y los Secrets del despliegue.') from None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
