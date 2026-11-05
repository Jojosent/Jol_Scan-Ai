"""Удаляет несохранённые черновики старше суток и их медиа."""
import sys
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import Report,db,utcnow


def prune_drafts() -> int:
    from flask import current_app
    old=db.session.scalars(db.select(Report).where(Report.saved.is_(False),Report.created_at<utcnow()-timedelta(hours=24))).all()
    tokens=[r.token for r in old]
    for report in old:db.session.delete(report)
    db.session.commit()
    for token in tokens:
        for kind in ('original','annotated'):
            (Path(current_app.config['UPLOAD_FOLDER'])/f'{token}_{kind}.jpg').unlink(missing_ok=True)
    return len(tokens)


if __name__=='__main__':
    app=create_app()
    with app.app_context():print(f'Removed drafts: {prune_drafts()}')
