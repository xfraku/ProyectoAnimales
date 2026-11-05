import io
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

import brain
import storage
from domain import DISCLAIMER
from reports import generate_report
from settings import AppError


def response_client(payload, finish='stop', refusal=None):
    message=SimpleNamespace(content=json.dumps(payload),refusal=refusal)
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_:SimpleNamespace(
        choices=[SimpleNamespace(message=message,finish_reason=finish)]))))


@pytest.mark.parametrize('state',['no_pertinente','incierta'])
def test_vision_rejects_before_classification(monkeypatch,image_bytes,state):
    monkeypatch.setattr(brain,'get_openai_client',lambda:response_client(dict(estado=state,motivo='Otra foto',urgente=False,motivo_urgencia='')))
    with pytest.raises(AppError,match='fotografía'): brain.validate_relevance(image_bytes)


def test_vision_valid_and_urgent(monkeypatch,image_bytes):
    monkeypatch.setattr(brain,'get_openai_client',lambda:response_client(dict(estado='apta',motivo='',urgente=True,motivo_urgencia='Herida preocupante')))
    assert brain.validate_relevance(image_bytes)['urgente'] is True


@pytest.mark.parametrize('payload,finish,refusal', [({},'stop',None),({'estado':'apta'},'stop',None),
    ({'estado':'apta','motivo':'','urgente':False,'motivo_urgencia':''},'length',None),({},'stop','refused')])
def test_malformed_or_failed_vision_does_not_pass(monkeypatch,image_bytes,payload,finish,refusal):
    monkeypatch.setattr(brain,'get_openai_client',lambda:response_client(payload,finish,refusal))
    with pytest.raises(AppError): brain.validate_relevance(image_bytes)


def test_api_failure_is_not_bad_image(monkeypatch,image_bytes):
    def broken(): raise TimeoutError('private API details')
    monkeypatch.setattr(brain,'get_openai_client',broken)
    with pytest.raises(AppError,match='consultar la IA') as err: brain.validate_relevance(image_bytes)
    assert 'private' not in str(err.value)


def test_chat_context_confidence_history_and_summary(monkeypatch):
    captured=[]
    def call(name,properties,messages,model):
        captured.append(messages)
        return {'respuesta':'Respuesta','urgente':True,'motivo_urgencia':'Dolor'} if name=='orientacion_canina' else {'resumen':'Resumen'}
    monkeypatch.setattr(brain,'structured_call',call)
    case=dict(label='Resultado no concluyente',diagnostico_ml='ringworm',confianza_ml=40,patient_snapshot={'nombre':'Luna'},advice='Revisar',alert_reason='')
    msgs=[{'role':'user','content':'Primer síntoma'},{'role':'assistant','content':'Primera respuesta'},
          {'role':'user','content':'Corrección posterior'},{'role':'assistant','content':'Consejo actualizado'}]
    assert brain.answer(case,msgs,'Nueva pregunta')['urgente']
    assert 'ringworm' not in json.dumps(captured[0]) and 'Primer síntoma' in json.dumps(captured[0],ensure_ascii=False)
    assert brain.summarize(case,msgs)=='Resumen'
    assert 'Consejo actualizado' in captured[1][-1]['content']


def test_s3_private_refs_and_errors(monkeypatch,image_bytes):
    monkeypatch.setenv('AWS_BUCKET_NAME','test-bucket')
    monkeypatch.setenv('AWS_REGION','us-east-2')
    calls=[]
    client=SimpleNamespace(put_object=lambda **kw:calls.append(kw),get_object=lambda **kw:{'Body':io.BytesIO(image_bytes),'ContentLength':len(image_bytes)},delete_object=lambda **kw:calls.append(kw))
    monkeypatch.setattr(storage,'client',lambda:client)
    ref=storage.upload_image(image_bytes,1,'00000000-0000-0000-0000-000000000001')
    assert ref.startswith('s3://test-bucket/consultas/')
    assert calls[0]['ContentType']=='image/jpeg' and 'ACL' not in calls[0]
    assert storage.read_image(ref)==image_bytes
    assert storage.object_key('https://test-bucket.s3.us-east-2.amazonaws.com/consultas/old.png')=='consultas/old.png'
    for bad in ['https://evil.example/consultas/test.jpg','s3://other/consultas/file','s3://test-bucket/private/key']:
        with pytest.raises(AppError): storage.read_image(bad)
    storage.delete_image(ref)
    pet_ref=storage.upload_image(image_bytes,1,'00000000-0000-0000-0000-000000000002','mascotas')
    assert pet_ref.startswith('s3://test-bucket/consultas/mascotas/')
    assert storage.object_key(pet_ref).startswith('consultas/')


def test_report_contains_full_conversation_unicode_and_image(image_bytes,tmp_path):
    case=dict(id=22,fecha=datetime(2026,11,5,12,30),patient_snapshot=dict(nombre='Pequeñita',raza='Mestiza',peso=10,tamano='Pequeño',color='Marrón',historial='Picazón desde ayer.'),
              diagnostico_ml='ringworm',confianza_ml=80,advice='Consulta al veterinario.',urgent=False)
    messages=[{'id':i,'role':'assistant' if i%2==0 else 'user','content':f'Mensaje {i}: orientación para Pequeñita. '+('Texto largo de prueba. '*100)} for i in range(1,7)]
    pdf=generate_report(case,messages,image_bytes)
    reader=PdfReader(io.BytesIO(pdf))
    text='\n'.join(p.extract_text() for p in reader.pages)
    assert len(reader.pages)>1 and any(len(p.images)>0 for p in reader.pages)
    for expected in ['Pequeñita','Tiña','Mensaje 1','Mensaje 6','No reemplaza el juicio de un veterinario colegiado.']:
        assert expected in text
    from pathlib import Path
    Path('test-output').mkdir(exist_ok=True)
    Path('test-output/reporte_ejemplo.pdf').write_bytes(pdf)
    case.update(confianza_ml=59,summary='RESUMEN DESACTUALIZADO',summary_message_id=2)
    text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(generate_report(case,[],None))).pages)
    assert 'Resultado no concluyente' in text and 'Tiña' not in text and 'RESUMEN DESACTUALIZADO' not in text
