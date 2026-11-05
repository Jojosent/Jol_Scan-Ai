"""Vercel entrypoint. The public showcase stores only regenerated demo data."""
from pathlib import Path
from tempfile import gettempdir

from app import create_app
from scripts.seed_demo import seed_demo

folder = Path(gettempdir()) / 'jolscan-showcase'
app = create_app({
    'SHOWCASE_ONLY': True,
    'INSTANCE_FOLDER': folder,
    'UPLOAD_FOLDER': folder,
    'SQLALCHEMY_DATABASE_URI': 'sqlite://',
    'GEMINI_API_KEY': '',
    'SESSION_COOKIE_SECURE': True,
})

with app.app_context():
    seed_demo(with_images=False)
