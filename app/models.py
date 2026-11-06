"""Сохранённые обращения, черновики анализа и отдельные дефекты."""
from datetime import datetime, timezone
import uuid
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, default=lambda: uuid.uuid4().hex, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    saved = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    district = db.Column(db.String(80), default='Анықталмаған')
    address = db.Column(db.String(200), default='')
    severity = db.Column(db.String(10), default='NONE')
    status = db.Column(db.String(16), default='new')
    summary = db.Column(db.Text, default='')
    recommendation = db.Column(db.Text, default='')
    inference_ms = db.Column(db.Integer, default=0)
    model = db.Column(db.String(100), default='')
    frame_second = db.Column(db.Float)
    detections = db.relationship('Detection', backref='report', cascade='all, delete-orphan', lazy='selectin')

    @property
    def priority(self) -> float:
        days = max(0, (utcnow() - self.created_at).total_seconds() / 86400)
        weight = {'NONE': 0, 'LOW': 1, 'MEDIUM': 3, 'HIGH': 5}[self.severity]
        return round(weight * len(self.detections) * (1 + days / 7), 1)

    def as_dict(self) -> dict:
        return {
            'id': self.id, 'token': self.token, 'created_at': self.created_at.isoformat() + 'Z',
            'latitude': self.latitude, 'longitude': self.longitude, 'district': self.district,
            'address': self.address, 'severity': self.severity, 'status': self.status,
            'summary': self.summary, 'recommendation': self.recommendation,
            'inference_ms': self.inference_ms, 'model': self.model, 'is_demo': self.is_demo,
            'count': len(self.detections), 'priority': self.priority, 'saved': self.saved,
            'frame_second': self.frame_second,
            'confidence': round(sum(d.confidence for d in self.detections) / len(self.detections), 3) if self.detections else None,
            'original_url': f'/media/{self.token}/original', 'annotated_url': f'/media/{self.token}/annotated',
            'detections': [d.as_dict() for d in self.detections],
        }


class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    area_ratio = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(10), nullable=False)
    box = db.Column(db.JSON, nullable=False)
    polygon = db.Column(db.JSON, nullable=False)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ('label', 'confidence', 'area_ratio', 'severity', 'box', 'polygon')}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    first_name = db.Column(db.String(80), nullable=False, default='')
    last_name = db.Column(db.String(80), nullable=False, default='')
    birth_date = db.Column(db.Date)
    phone = db.Column(db.String(32), nullable=False, default='')
    bio = db.Column(db.String(500), nullable=False, default='')
    avatar = db.deferred(db.Column(db.LargeBinary))


class ReportAuthor(db.Model):
    """Связь с автором без изменения таблицы старых заявок."""
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)


class ReportPhoto(db.Model):
    report_id = db.Column(db.Integer, db.ForeignKey('report.id', ondelete='CASCADE'), primary_key=True)
    kind = db.Column(db.String(12), primary_key=True)
    data = db.Column(db.LargeBinary, nullable=False)
