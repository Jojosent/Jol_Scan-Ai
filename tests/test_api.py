"""Проверка полного цикла с подменой лишь сетевого ответа Gemini."""
import io
from PIL import Image
from app.models import Report, db


def analyze(client,headers,image_bytes):
    return client.post('/api/detect',headers=headers,data={'file':(io.BytesIO(image_bytes),'road.jpg')})


def save(client,headers,token,**extra):
    return client.post('/api/reports',headers=headers,json={'token':token,'latitude':51.12,'longitude':71.45,**extra})


def test_pages(client):
    for path in ['/','/analyze','/map','/dashboard','/reports','/settings']:
        result=client.get(path)
        assert result.status_code==200
        assert b'lang="kk"' in result.data


def test_end_to_end(client,app,headers,image_bytes,gemini_mock):
    result=analyze(client,headers,image_bytes)
    assert result.status_code==201
    report=result.json['results'][0]
    assert report['count']==1 and report['severity']=='HIGH'
    assert client.get('/api/stats').json['total']==0
    original=client.get(report['original_url'])
    assert original.status_code==200 and not Image.open(io.BytesIO(original.data)).getexif()
    assert save(client,headers,report['token'],address='Тест көшесі').status_code==201
    assert save(client,headers,report['token']).status_code==200
    assert client.get('/api/stats').json['total']==1
    assert len(client.get('/api/reports?severity=HIGH').json['reports'])==1
    assert not client.get('/api/reports?severity=LOW').json['reports']
    path=f'/api/reports/{report["id"]}/status'
    assert client.patch(path,headers=headers,json={'status':'repaired'}).status_code==409
    assert client.patch(path,headers=headers,json={'status':'in_progress'}).status_code==200
    assert client.patch(path,headers=headers,json={'status':'repaired'}).status_code==200
    assert client.get('/api/stats').json['repaired']==1
    assert client.get('/export/csv').data.startswith(b'\xef\xbb\xbf')


def test_no_fake_inference_without_key(client,app,headers,image_bytes):
    app.config['GEMINI_API_KEY']=''
    response=analyze(client,headers,image_bytes)
    assert response.status_code==503
    assert client.get('/api/stats').json['total']==0


def test_no_defects(client,headers,image_bytes,gemini_mock):
    gemini_mock['defects']=[]
    result=analyze(client,headers,image_bytes).json['results'][0]
    assert result['count']==0 and result['severity']=='NONE' and result['confidence'] is None


def test_upload_validation(client,headers,image_bytes):
    assert client.post('/api/detect',data={'file':(io.BytesIO(image_bytes),'road.jpg')}).status_code==403
    assert client.post('/api/detect',headers=headers,data={}).status_code==400
    assert client.post('/api/detect',headers=headers,data={'file':(io.BytesIO(b'bad'),'x.jpg')}).status_code==400
    assert client.post('/api/detect',headers=headers,data={'file':(io.BytesIO(b'x'),'x.exe')}).status_code==400
    assert client.post('/api/detect',headers=headers,data={'file':(io.BytesIO(b'x'*(15*1024*1024+1)),'x.jpg')}).status_code==413


def test_invalid_filters(client):
    for query in ['severity=INVALID','status=broken','from=bad','from=2026-12-01&to=2026-01-01']:
        assert client.get('/api/reports?'+query).status_code==400


def test_draft_ownership_and_gps(client,app,headers,image_bytes,gemini_mock):
    report=analyze(client,headers,image_bytes).json['results'][0]
    other=app.test_client();csrf=other.get('/api/session').json['csrf_token']
    other.post('/register',data={'email':'other@example.test','password':'test-password','csrf_token':csrf})
    csrf=other.get('/api/session').json['csrf_token']
    assert save(other,{'X-CSRF-Token':csrf},report['token']).status_code==403
    assert save(client,headers,report['token'],latitude='NaN').status_code==400
    assert save(client,headers,report['token'],latitude=None).status_code==400


def test_provider_errors(client,headers,image_bytes,monkeypatch):
    import requests
    def timeout(*args,**kwargs):raise requests.Timeout()
    monkeypatch.setattr('app.ai.detector.requests.post',timeout)
    result=analyze(client,headers,image_bytes)
    assert result.status_code==502
    assert 'test-key' not in result.get_data(as_text=True)


def test_transient_provider_error_retries(client,headers,image_bytes,gemini_mock,monkeypatch):
    import json
    calls=[]
    class Response:
        def __init__(self,status):self.status_code=status
        def json(self):
            if self.status_code != 200:return {'error':{'message':'Service overloaded'}}
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(gemini_mock)}]}}]}
    def post(*args,**kwargs):
        calls.append(1)
        return Response(503 if len(calls)<3 else 200)
    monkeypatch.setattr('app.ai.detector.requests.post',post)
    monkeypatch.setattr('app.ai.detector.time.sleep',lambda _:None)
    response=analyze(client,headers,image_bytes)
    assert response.status_code==201 and len(calls)==3


def test_permanent_provider_error_is_not_retried(client,headers,image_bytes,monkeypatch):
    calls=[]
    class Response:
        status_code=403
        def json(self):return {'error':{'message':'Invalid key'}}
    def post(*args,**kwargs):calls.append(1);return Response()
    monkeypatch.setattr('app.ai.detector.requests.post',post)
    assert analyze(client,headers,image_bytes).status_code==502
    assert len(calls)==1


def test_demo_cleanup_preserves_real(client,app,headers):
    with app.app_context():
        db.session.add_all([Report(saved=True,is_demo=True),Report(saved=True,is_demo=False)])
        db.session.commit()
    response=client.delete('/api/demo',headers=headers)
    assert response.status_code==200 and response.json['deleted']==1
    assert client.get('/api/stats').json['total']==1


def test_admin_permissions(client,app,headers):
    guest=app.test_client()
    csrf=guest.get('/api/session').json['csrf_token']
    guest.post('/register',data={'email':'resident@example.test','password':'test-password','csrf_token':csrf,'is_admin':'true'})
    csrf=guest.get('/api/session').json['csrf_token']
    assert guest.get('/admin').status_code==403
    assert guest.get('/api/reports').status_code==403
    assert guest.get('/export/pdf').status_code==403
    assert guest.delete('/api/demo',headers={'X-CSRF-Token':csrf}).status_code==403
    assert client.delete('/api/demo',headers=headers).status_code==200


def test_pdf(client,headers,image_bytes,gemini_mock):
    report=analyze(client,headers,image_bytes).json['results'][0]
    save(client,headers,report['token'])
    response=client.get('/export/pdf')
    assert response.status_code==200 and response.data.startswith(b'%PDF-')


def test_seed_is_idempotent(app,client,headers):
    from scripts.seed_demo import seed_demo
    with app.app_context():
        assert seed_demo()==40
        assert seed_demo()==0
    stats=client.get('/api/stats').json
    assert stats['demo']==40 and stats['total']==40
    assert len(client.get('/api/reports').json['reports'])==40


def test_video_sampling(client,app,headers,tmp_path,gemini_mock):
    import cv2
    import numpy as np
    path=tmp_path/'clip.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),20,(160,120))
    assert writer.isOpened()
    for _ in range(60):writer.write(np.full((120,160,3),100,dtype=np.uint8))
    writer.release()
    response=client.post('/api/detect',headers=headers,data={'file':(io.BytesIO(path.read_bytes()),'clip.mp4'),'frame_step':'20'})
    assert response.status_code==201
    assert [r['frame_second'] for r in response.json['results']]==[0,1,2]


def test_failed_video_rolls_back(client,app,headers,tmp_path,monkeypatch):
    import cv2
    import numpy as np
    from app.ai.detector import DetectorError
    path=tmp_path/'clip.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),20,(160,120))
    for _ in range(40):writer.write(np.full((120,160,3),100,dtype=np.uint8))
    writer.release()
    counter=[0]
    def detector(image):
        counter[0]+=1
        if counter[0]>1:raise DetectorError('Test failure')
        return {'summary':'Тест','recommendation':'','detections':[],'inference_ms':1,'model':'mock'}
    monkeypatch.setattr('app.routes.api.detect',detector)
    response=client.post('/api/detect',headers=headers,data={'file':(io.BytesIO(path.read_bytes()),'clip.mp4'),'frame_step':'20'})
    assert response.status_code==502
    assert not list(app.config['UPLOAD_FOLDER'].glob('*.jpg'))
    with app.app_context():assert db.session.scalar(db.select(db.func.count(Report.id)))==0
