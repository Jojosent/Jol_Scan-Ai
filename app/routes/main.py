"""Страницы казахского интерфейса и обезличенные медиафайлы."""
from pathlib import Path
from urllib.parse import urlsplit
from flask import Blueprint, current_app, g, redirect, render_template, request, send_file, abort, session
from app.localization import LANGUAGES
from app.models import Report, db

bp = Blueprint('main', __name__)


@bp.get('/')
def index():
    return render_template('index.html', page='home')


@bp.get('/analyze')
def analyze():
    if not current_app.config.get('SHOWCASE_ONLY') and not g.user:
        return redirect('/login?next=/analyze')
    return render_template('analyze.html', page='analyze')


@bp.get('/map')
def map_page():
    return render_template('map.html', page='map')


@bp.get('/settings')
def settings():
    return render_template('settings.html', page='settings')


@bp.get('/demo')
def demo():
    return render_template('demo.html', page='demo')


@bp.post('/preferences')
def preferences():
    target = request.form.get('return_to', '/')
    try:
        parts = urlsplit(target)
    except ValueError:
        abort(400)
    routes = {'/', '/analyze', '/map', '/dashboard', '/settings', '/demo', '/admin', '/reports', '/login', '/register', '/profile'}
    if target.startswith('//') or '\\' in target or parts.netloc or parts.scheme or parts.path not in routes:
        target = '/'
    response = redirect(target)
    for form_field, values in [('language', LANGUAGES), ('theme', {'light', 'dark'})]:
        value = request.form.get(form_field)
        if value in values:
            response.set_cookie(f'jolscan_{form_field}', value, max_age=365 * 86400, samesite='Lax', httponly=True)
    return response


@bp.get('/media/<token>/<kind>')
def media(token: str, kind: str):
    if kind not in {'original', 'annotated'} or len(token) != 32:
        abort(404)
    report = db.session.scalar(db.select(Report).where(Report.token == token))
    if not report:
        abort(404)
    if not (g.user and (g.user.is_admin or report.token in session.get('drafts', []))):
        abort(404)
    path = Path(current_app.config['UPLOAD_FOLDER']) / f'{report.token}_{kind}.jpg'
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype='image/jpeg')
