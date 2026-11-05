"""Фабрика Flask-приложения и общие проверки безопасности."""
import json
import secrets
from pathlib import Path
from flask import Flask, g, jsonify, request, session
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException
from .localization import CATALOG, language, translate
from .models import db


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv()
    from .config import Config
    instance_folder = (test_config or {}).get('INSTANCE_FOLDER')
    app = Flask(__name__, instance_path=str(instance_folder) if instance_folder else None)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    db.init_app(app)
    from .routes.main import bp as main
    from .routes.api import bp as api
    from .routes.dashboard import bp as dashboard
    from .routes.accounts import bp as accounts
    app.register_blueprint(main)
    app.register_blueprint(api)
    app.register_blueprint(dashboard)
    app.register_blueprint(accounts)
    with app.app_context():
        db.create_all()
    translations = json.loads((Path(__file__).parent / 'i18n/kk.json').read_text(encoding='utf-8'))
    translations.update(nav_demo='Көрсетілім', nav_login='Кіру', nav_register='Тіркелу', nav_profile='Профиль', nav_error='Қате')

    @app.before_request
    def protect_mutations():
        if app.config.get('SHOWCASE_ONLY') and request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.path != '/preferences':
            from flask import abort
            abort(403)
        if request.method in {'POST', 'PATCH', 'DELETE', 'PUT'}:
            supplied = request.headers.get('X-CSRF-Token', '')
            if not request.path.startswith('/api/'):
                supplied = request.form.get('csrf_token', '')
            expected = session.get('csrf_token', '')
            if not expected or not secrets.compare_digest(supplied, expected):
                return jsonify(error=translate(translations['csrf_error'])), 403

    @app.context_processor
    def inject_context() -> dict:
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(24)
        return {'t': lambda key: translate(translations.get(key, key)), 'tr': translate,
                'language': language(), 'client_catalog': CATALOG[language()],
                'carto_key': app.config['CARTO_BASEMAP_KEY'], 'showcase_only': app.config.get('SHOWCASE_ONLY', False),
                'theme': 'dark' if request.cookies.get('jolscan_theme') == 'dark' else 'light',
                'csrf_token': session['csrf_token'],
                'ai_ready': bool(app.config['GEMINI_API_KEY']), 'gemini_model': app.config['GEMINI_MODEL']}

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            message = translations['too_large'] if error.code == 413 else translations.get(f'error_{error.code}', error.description)
            return jsonify(error=translate(message)), error.code
        from flask import render_template
        return render_template('error.html', page='error', code=error.code), error.code

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.path.startswith(('/api/', '/media/', '/admin', '/profile', '/export/')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app
