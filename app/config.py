"""Настройки сервера, Gemini и приближённых географических зон."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{(ROOT / "instance/jolscan.db").as_posix()}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024
    UPLOAD_FOLDER = ROOT / 'uploads'
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
    CARTO_BASEMAP_KEY = os.getenv('CARTO_BASEMAP_KEY', '')
    GEOCODER_URL = os.getenv('GEOCODER_URL', 'https://photon.komoot.io/api/')
    VIDEO_FRAME_STEP = int(os.getenv('VIDEO_FRAME_STEP', '30'))
    MAX_VIDEO_FRAMES = int(os.getenv('MAX_VIDEO_FRAMES', '5'))
    MAX_VIDEO_SECONDS = int(os.getenv('MAX_VIDEO_SECONDS', '30'))
    GEMINI_TIMEOUT = 65
    HIGH_AREA_THRESHOLD = 0.08
    MEDIUM_AREA_THRESHOLD = 0.025
    MIN_CONFIDENCE = 0.4
    # Пересекающиеся прямоугольники дают лишь приблизительный район.
    DISTRICT_BOXES = [
        ('Нұра', (51.04, 71.28, 51.145, 71.42)),
        ('Есіл', (51.02, 71.42, 51.145, 71.56)),
        ('Байқоңыр', (51.17, 71.42, 51.27, 71.53)),
        ('Сарыарқа', (51.145, 71.28, 51.27, 71.42)),
        ('Алматы', (51.145, 71.42, 51.24, 71.62)),
    ]
