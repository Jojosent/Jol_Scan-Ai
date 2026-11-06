"""Browser-facing account forms and private report boundaries."""
import io

from app.models import Report, User, db


def test_registration_profile_and_logout(app, image_bytes):
    browser = app.test_client()
    csrf = browser.get('/api/session').json['csrf_token']
    response = browser.post('/register', data={
        'email': 'RESIDENT@example.test', 'password': 'test-password', 'csrf_token': csrf,
    })
    assert response.location == '/profile'
    csrf = browser.get('/api/session').json['csrf_token']
    response = browser.post('/profile', data={
        'csrf_token': csrf, 'first_name': 'Dana', 'avatar': (io.BytesIO(image_bytes), 'profile.jpg'),
    })
    assert response.status_code == 302
    assert browser.get('/profile/avatar').mimetype == 'image/jpeg'
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == 'resident@example.test'))
        assert user.first_name == 'Dana' and user.birth_date is None
        assert not user.is_admin and user.password_hash != 'test-password'
    browser.post('/logout', data={'csrf_token': csrf})
    assert browser.get('/profile').location == '/login?next=/profile'
    assert browser.get('/profile/avatar').status_code == 404


def test_public_map_shows_addresses_and_status_without_private_fields(app, client):
    with app.app_context():
        private = Report(saved=True, latitude=51.2, longitude=71.4, status='in_progress',
                         address='Кабанбай батыра 53')
        demo = Report(saved=True, is_demo=True, latitude=51.1, longitude=71.3)
        db.session.add_all([private, demo])
        db.session.commit()
        token = private.token
    (app.config['UPLOAD_FOLDER'] / f'{token}_original.jpg').write_bytes(b'sample')
    guest = app.test_client()
    reports = guest.get('/api/map').json['reports']
    assert len(reports) == 2
    real = next(report for report in reports if not report['is_demo'])
    assert real['address'] == 'Кабанбай батыра 53' and real['status'] == 'in_progress'
    assert {'token', 'annotated_url', 'summary'}.isdisjoint(real)
    assert guest.get('/api/map?status=in_progress').json['reports'] == [real]
    assert guest.get(f'/media/{token}/original').status_code == 404
    assert client.get(f'/media/{token}/original').status_code == 200


def test_preferences_persist_across_pages(app):
    guest = app.test_client()
    csrf = guest.get('/api/session').json['csrf_token']
    response = guest.post('/preferences', data={
        'csrf_token': csrf, 'language': 'en', 'theme': 'light', 'return_to': '/demo',
    }, follow_redirects=True)
    assert b'lang="en" data-theme="light"' in response.data
    assert b'How does one photo lead to a repair?' in response.data
    assert b'Sign in' in guest.get('/login').data
    response = guest.post('/preferences', data={
        'csrf_token': csrf, 'language': 'ru', 'return_to': '//example.test',
    })
    assert response.location == '/'
    assert b'lang="ru" data-theme="light"' in guest.get('/').data
