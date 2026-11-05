"""Private S3 objects. Persistent references are not public or expiring URLs."""
import logging
from urllib.parse import unquote, urlparse

import boto3
from botocore.config import Config

from settings import AppError, setting

log = logging.getLogger(__name__)


def client():
    return boto3.client('s3', region_name=setting('AWS_REGION', 'us-east-2'),
        aws_access_key_id=setting('AWS_ACCESS_KEY_ID'), aws_secret_access_key=setting('AWS_SECRET_ACCESS_KEY'),
        config=Config(connect_timeout=5, read_timeout=15, retries={'max_attempts': 2}))


def bucket():
    value = setting('AWS_BUCKET_NAME')
    if not value:
        raise AppError('El almacenamiento de imágenes no está configurado.')
    return value


def object_key(ref):
    parsed = urlparse(ref or '')
    name = bucket()
    if parsed.scheme == 's3' and parsed.netloc == name:
        key = parsed.path.lstrip('/')
    elif parsed.scheme == 'https' and parsed.hostname in (
        f'{name}.s3.amazonaws.com', f'{name}.s3.{setting("AWS_REGION", "us-east-2")}.amazonaws.com'):
        key = unquote(parsed.path.lstrip('/'))
    else:
        raise AppError('La referencia de la imagen no pertenece al almacenamiento configurado.')
    if not key.startswith(('consultas/', 'mascotas/')) or '..' in key.split('/'):
        raise AppError('La ruta de la imagen no es válida.')
    return key


def upload_image(data, user_id, request_id, prefix='consultas'):
    from uuid import UUID
    if prefix not in ('consultas', 'mascotas'):
        raise AppError('Destino de imagen inválido.')
    # The original IAM policy already permits consultas/*; profile photos use it too.
    folder = 'consultas/mascotas' if prefix == 'mascotas' else 'consultas'
    key = f'{folder}/u{int(user_id)}/{UUID(str(request_id))}.jpg'
    try:
        client().put_object(Bucket=bucket(), Key=key, Body=data, ContentType='image/jpeg',
                            ServerSideEncryption='AES256')
        return f's3://{bucket()}/{key}'
    except AppError:
        raise
    except Exception as exc:
        log.warning('S3 upload failed: %s', type(exc).__name__)
        raise AppError('No se pudo guardar la imagen. Inténtalo de nuevo.') from None


def read_image(ref):
    key = object_key(ref)
    try:
        result = client().get_object(Bucket=bucket(), Key=key)
        body = result['Body']
        try:
            if result.get('ContentLength', 0) > 20 * 1024 * 1024:
                raise AppError('La imagen guardada supera el tamaño permitido.')
            data = body.read(20 * 1024 * 1024 + 1)
            if len(data) > 20 * 1024 * 1024:
                raise AppError('La imagen guardada supera el tamaño permitido.')
            return data
        finally:
            body.close()
    except AppError:
        raise
    except Exception as exc:
        log.warning('S3 read failed: %s', type(exc).__name__)
        raise AppError('No se pudo recuperar la fotografía. Puedes reintentar o descargar el reporte sin imagen.') from None


def delete_image(ref):
    key = object_key(ref)
    try:
        client().delete_object(Bucket=bucket(), Key=key)
    except Exception as exc:
        log.warning('S3 deletion failed: %s', type(exc).__name__)
        raise AppError('No se pudo eliminar el archivo del almacenamiento.') from None
