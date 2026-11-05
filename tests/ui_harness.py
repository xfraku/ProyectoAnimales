"""Local browser QA only. No public deployment; no real S3/OpenAI calls."""
import io
import os
import runpy
import sys
from pathlib import Path

if os.environ.get('PETSKIN_UI_TEST') != '1' or os.environ.get('DB_HOST') != '127.0.0.1' or os.environ.get('DB_NAME') != 'petskin_test':
    raise RuntimeError('The UI harness requires the explicit isolated local test configuration.')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import brain
import storage
from settings import AppError


def photo():
    image=Image.new('RGB',(600,400),(186,150,112))
    output=io.BytesIO();image.save(output,'JPEG');return output.getvalue()


def relevance(data):
    pixel=Image.open(io.BytesIO(data)).getpixel((0,0))
    if pixel[0]>220 and pixel[1]<30:
        raise AppError('La imagen no es pertinente para el análisis canino. Selecciona otra fotografía.')
    return dict(estado='apta',motivo='',urgente=False,motivo_urgencia='',model='mock-ui')


brain.validate_relevance=relevance
brain.predict=lambda _:('Dermatitis',74.25)
brain.answer=lambda *a:dict(respuesta='Mantén la zona limpia y evita productos irritantes. Consulta al veterinario para confirmar la causa de la picazón.',urgente=False,motivo_urgencia='')
brain.summarize=lambda *a:'Se informó picazón. Se orientó sobre cuidados generales y consulta veterinaria para confirmar la causa.'
storage.read_image=lambda _:photo()
storage.upload_image=lambda data,user_id,request_id,prefix='consultas':f's3://test-bucket/{prefix}/u{user_id}/{request_id}.jpg'
storage.delete_image=lambda _:None
runpy.run_path(str(Path(__file__).resolve().parents[1]/'app.py'),run_name='__main__')
