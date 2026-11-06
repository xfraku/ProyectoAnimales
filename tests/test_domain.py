import io
import math

import pytest
from PIL import Image

from domain import *
from settings import AppError


@pytest.mark.parametrize('email', ['', 'a', 'a@', 'a@@b.com', 'a b@domain.com', 'a@domain', 'a@.com', 'a@dom..com'])
def test_invalid_email(email):
    with pytest.raises(AppError): email_address(email)


def test_email_normalization():
    assert email_address(' TEST@Example.COM ') == 'test@example.com'


@pytest.mark.parametrize('weight', [0, -1, 4000, float('nan'), float('inf'), 'texto'])
def test_unrealistic_weight(weight):
    with pytest.raises(AppError): pet_fields('Luna','Mestizo',weight,'Pequeño')


@pytest.mark.parametrize('name,breed', [('', 'Mestizo'), ('  ', 'Mestizo'), ('Luna', ''), ('Luna', '  ')])
def test_pet_required_fields(name,breed):
    with pytest.raises(AppError): pet_fields(name,breed,5,'Pequeño')


def test_threshold_boundary_and_spanish():
    assert diagnosis('ringworm',59.999) == 'Resultado no concluyente'
    assert diagnosis('ringworm',60) == 'Tiña'
    assert diagnosis('Healthy',99) == 'Sin signos detectados por el modelo'
    assert diagnosis('unknown',99) == 'Resultado no concluyente'
    assert diagnosis('ringworm',float('nan')) == 'Resultado no concluyente'


def test_images_rgb_and_strip_metadata():
    for mode in ['L', 'RGBA', 'RGB']:
        out=io.BytesIO();Image.new(mode,(80,90)).save(out,'PNG')
        result=validate_image(out.getvalue(),'foto.PNG')
        image=Image.open(io.BytesIO(result))
        assert image.mode=='RGB' and image.format=='JPEG' and not image.getexif()


@pytest.mark.parametrize('data,name',[(b'%PDF-123','foto.pdf'),(b'not image','foto.jpg'),(b'', 'foto.jpg'),(b'x'*(MAX_IMAGE_BYTES+1),'foto.png')])
def test_bad_images(data,name):
    with pytest.raises(AppError): validate_image(data,name)


def test_small_large_and_disguised_images():
    for size,fmt in [((63,120),'PNG'),((5000,5000),'PNG'),((100,100),'GIF')]:
        out=io.BytesIO();Image.new('RGB',size).save(out,fmt)
        with pytest.raises(AppError): validate_image(out.getvalue(),'foto.png')


def test_whatsapp_link():
    assert whatsapp_url('+1 (202) 555-0123') == 'https://wa.me/12025550123'
    for invalid in ('', None, 'contacto', '0012025550123', '123?text=hola', '1' * 16):
        assert whatsapp_url(invalid) is None


def test_password_and_multiline_question():
    with pytest.raises(AppError): password_bytes('')
    with pytest.raises(AppError): password_bytes('ñ'*37)
    assert required_text('Hoy se rasca.\nNo tiene fiebre.', 'Consulta',4000).count('\n')==1
