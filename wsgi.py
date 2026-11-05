"""Vercel entrypoint. The public showcase stores only regenerated demo data."""
import os
from pathlib import Path
from tempfile import gettempdir

from app import create_app

if os.environ.get('VERCEL'):
    folder = Path(gettempdir()) / 'jolscan-showcase'
    app = create_app({
        'SHOWCASE_ONLY': True,
        'INSTANCE_FOLDER': folder,
        'UPLOAD_FOLDER': folder,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'GEMINI_API_KEY': '',
        'SESSION_COOKIE_SECURE': True,
    })
    from scripts.seed_demo import seed_demo

    with app.app_context():
        seed_demo(with_images=False)
else:
    app = create_app()
