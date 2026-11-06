"""Store sanitized report media in PostgreSQL or the local uploads directory."""
from io import BytesIO
from pathlib import Path

from flask import current_app

from app.models import Report, ReportPhoto, db


def photo_path(token: str, kind: str) -> Path:
    return Path(current_app.config['UPLOAD_FOLDER']) / f'{token}_{kind}.jpg'


def save_photo(report: Report, kind: str, image, quality: int = 90) -> None:
    if current_app.config.get('DATABASE_MEDIA'):
        buffer = BytesIO()
        image.save(buffer, 'JPEG', quality=quality)
        db.session.add(ReportPhoto(report_id=report.id, kind=kind, data=buffer.getvalue()))
    else:
        image.save(photo_path(report.token, kind), 'JPEG', quality=quality)


def read_photo(report: Report, kind: str) -> Path | BytesIO | None:
    if current_app.config.get('DATABASE_MEDIA'):
        photo = db.session.get(ReportPhoto, (report.id, kind))
        return BytesIO(photo.data) if photo else None
    path = photo_path(report.token, kind)
    return path if path.is_file() else None
