"""Изолированная SQLite-база и реальные локальные изображения."""
import io
import pytest
from PIL import Image
from app import create_app
from app.models import User, db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite://','UPLOAD_FOLDER':tmp_path,
                    'GEMINI_API_KEY':'test-key','SECRET_KEY':'test-secret'})
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove();db.drop_all()


@pytest.fixture
def client(app):
    client = app.test_client()
    with app.app_context():
        admin = User(email='test-admin@example.test', password_hash=generate_password_hash('test-password'), is_admin=True)
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    with client.session_transaction() as browser_session:
        browser_session['user_id'] = admin_id
    return client


@pytest.fixture
def headers(client):
    return {'X-CSRF-Token':client.get('/api/session').json['csrf_token']}


@pytest.fixture
def image_bytes():
    stream=io.BytesIO()
    image=Image.new('RGB',(640,480),'#53575b')
    exif=Image.Exif();exif[271]='Private device';exif[315]='Private author'
    image.save(stream,'JPEG',exif=exif)
    return stream.getvalue()


@pytest.fixture
def gemini_mock(monkeypatch):
    import json
    body={'summary':'Жолда бір ақау бар.','recommendation':'Учаскені тексеру қажет.',
          'defects':[{'label':'Шұңқыр','confidence':.91,'box':[200,200,700,700],
                       'polygon':[[200,200],[700,200],[700,700],[200,700]]}]}
    class Response:
        status_code=200
        def json(self):
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(body)}]}}]}
    monkeypatch.setattr('app.ai.detector.requests.post',lambda *args,**kwargs:Response())
    return body
