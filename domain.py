"""Pure validation and display rules. Never use classifier confidence as accuracy."""
import io
import math
import warnings
import re

from email_validator import EmailNotValidError, validate_email
from PIL import Image, ImageOps, UnidentifiedImageError

from settings import AppError

CLASSES = ('Dermatitis', 'Fungal_infections', 'Healthy', 'Hypersensitivity', 'demodicosis', 'ringworm')
LABELS = dict(zip(CLASSES, ('Dermatitis', 'Infección por hongos', 'Sin signos detectados por el modelo',
                           'Hipersensibilidad', 'Demodicosis', 'Tiña')))
THRESHOLD = 60.0
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
TERMS_VERSION = '2026-11-06'
ROLES = ('user', 'especialista', 'admin')
ROLE_LABELS = {'user': 'Usuario', 'especialista': 'Especialista', 'admin': 'Administrador'}
DISCLAIMER = ('AVISO: Este reporte es una sugerencia basada en IA. '
              'No reemplaza el juicio de un veterinario colegiado.')
INVALID_LOGIN = 'Credenciales inválidas. Por favor, inténtalo de nuevo.'


def required_text(value, label, maximum=100):
    value = str(value or '').strip()
    if not value:
        raise AppError(f'El campo {label} es obligatorio.')
    if len(value) > maximum or any(ord(c) < 32 and not (maximum > 100 and c in '\n\t\r') for c in value):
        raise AppError(f'{label}: utiliza hasta {maximum} caracteres, sin caracteres de control.')
    return value


def email_address(value):
    if not str(value or '').strip():
        raise AppError('Completa el campo Correo electrónico; es obligatorio.')
    try:
        result = validate_email(str(value or '').strip(), check_deliverability=False)
    except EmailNotValidError:
        raise AppError('Ingresa un correo electrónico de formato válido, por ejemplo nombre@dominio.com.') from None
    if len(result.normalized) > 100:
        raise AppError('El correo electrónico no puede superar 100 caracteres.')
    return result.normalized.lower()


def password_bytes(value):
    if not value or not value.strip():
        raise AppError('La contraseña es obligatoria.')
    data = value.encode('utf-8')
    if len(data) > 72:
        raise AppError('La contraseña es demasiado larga (máximo 72 bytes en UTF-8).')
    return data


def pet_fields(nombre, raza, peso, tamano, historial='', color=''):
    nombre = required_text(nombre, 'Nombre')
    raza = required_text(raza, 'Raza')
    try:
        peso = float(peso)
    except (ValueError, TypeError):
        raise AppError('Ingresa un peso numérico en kilogramos.') from None
    if not math.isfinite(peso) or not 0.1 <= peso <= 120:
        raise AppError('El peso debe estar entre 0,1 y 120 kg.')
    if tamano not in ('Pequeño', 'Mediano', 'Grande'):
        raise AppError('Selecciona un tamaño válido.')
    if len(historial or '') > 5000 or len(color or '') > 100:
        raise AppError('Las notas admiten hasta 5000 caracteres y el color hasta 100.')
    return dict(nombre=nombre, raza=raza, peso=peso, tamano=tamano,
                historial=(historial or '').strip(), color=(color or '').strip())


def diagnosis(code, confidence):
    if confidence is None or not math.isfinite(float(confidence)) or float(confidence) < THRESHOLD:
        return 'Resultado no concluyente'
    return LABELS.get(code, 'Resultado no concluyente')


def validate_image(data, filename):
    """Decode fully and re-encode RGB, stripping EXIF including GPS metadata."""
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError('El tamaño de la imagen excede a lo permitido (máximo 20 MB). Selecciona una más pequeña.')
    if not data or not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise AppError('Formato no válido. Selecciona una imagen JPG, JPEG o PNG.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in ('JPEG', 'PNG'):
                    raise AppError('El contenido del archivo debe ser una imagen JPG o PNG real.')
                if original.width * original.height > MAX_IMAGE_PIXELS:
                    raise AppError('La imagen es demasiado grande. Reduce su resolución a menos de 24 megapíxeles.')
                if min(original.size) < 64:
                    raise AppError('La imagen es demasiado pequeña. Utiliza una fotografía de al menos 64 × 64 píxeles.')
                original.load()
                img = ImageOps.exif_transpose(original).convert('RGB')
                img.thumbnail((1800, 1800))
                out = io.BytesIO()
                img.save(out, 'JPEG', quality=92)
                return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise AppError('No se puede leer la imagen. Puede estar dañada; selecciona otra fotografía JPG o PNG.') from None


def whatsapp_url(phone):
    """Build a click-to-chat URL from an international contact number."""
    digits = re.sub(r'[ ()-]', '', str(phone or '').strip()).removeprefix('+')
    if re.fullmatch(r'[1-9][0-9]{6,14}', digits):
        return f'https://wa.me/{digits}'
    return None
