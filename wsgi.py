"""Vercel entrypoint. Enable accounts and report media with managed PostgreSQL."""
import os
from pathlib import Path
from tempfile import gettempdir

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app
from app.models import User, db
from scripts.seed_demo import seed_demo

folder = Path(gettempdir()) / 'jolscan-showcase'
database_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
database = make_url(database_url).set(drivername='postgresql+psycopg') if database_url else 'sqlite://'
app = create_app({
    'SHOWCASE_ONLY': not database_url,
    'DATABASE_MEDIA': bool(database_url),
    'INSTANCE_FOLDER': folder,
    'UPLOAD_FOLDER': folder,
    'SQLALCHEMY_DATABASE_URI': database,
    'SQLALCHEMY_ENGINE_OPTIONS': {'pool_pre_ping': True} if database_url else {},
    'UPLOAD_LIMIT_MB': 4,
    'MAX_CONTENT_LENGTH': 4_300_000,
    'SESSION_COOKIE_SECURE': True,
})

with app.app_context():
    if database_url:
        db.session.execute(text('SELECT pg_advisory_xact_lock(71420302)'))
        email = os.getenv('JOLSCAN_ADMIN_EMAIL', '').strip().lower()
        password_hash = os.getenv('JOLSCAN_ADMIN_HASH', '')
        if email and password_hash and not db.session.scalar(db.select(User.id).where(User.email == email)):
            db.session.add(User(email=email, password_hash=password_hash, is_admin=True))
            seed_demo()
        db.session.commit()
    else:
        seed_demo(with_images=False)
