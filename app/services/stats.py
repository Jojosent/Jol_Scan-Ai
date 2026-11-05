"""Агрегация только сохранённых обращений, включая явно отмеченные демо."""
from collections import Counter
from datetime import timedelta
from app.models import Report, db, utcnow


def get_stats(demo_only: bool = False) -> dict:
    query = db.select(Report).where(Report.saved.is_(True))
    if demo_only:
        query = query.where(Report.is_demo.is_(True))
    reports = db.session.scalars(query).all()
    by_severity = Counter(r.severity for r in reports)
    by_status = Counter(r.status for r in reports)
    by_district = Counter(r.district for r in reports)
    by_day = Counter(r.created_at.strftime('%Y-%m-%d') for r in reports)
    today = utcnow().date()
    days = [str(today - timedelta(days=i)) for i in reversed(range(14))]
    return dict(total=len(reports), defects=sum(len(r.detections) for r in reports),
                critical=by_severity['HIGH'], repaired=by_status['repaired'],
                demo=sum(r.is_demo for r in reports), active=sum(r.status != 'repaired' for r in reports),
                severity={k: by_severity[k] for k in ('LOW', 'MEDIUM', 'HIGH', 'NONE')},
                status={k: by_status[k] for k in ('new', 'in_progress', 'repaired')},
                districts=dict(by_district), days=[{'date': d, 'count': by_day[d]} for d in days])
