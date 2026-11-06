"""REST API: анализ, сохранение геолокации, фильтры и статусы."""
import io
import math
import tempfile
import requests
from datetime import datetime, timedelta
from pathlib import Path
import cv2
from PIL import Image, UnidentifiedImageError
from flask import Blueprint, abort, current_app, g, jsonify, request, session
from app.ai.detector import DetectorError, annotate, detect
from app.ai.privacy import sanitize
from app.localization import LANGUAGES, language, translate
from app.models import Detection, Report, ReportAuthor, db, utcnow
from app.routes.accounts import require_admin, require_user
from app.services.geo import district_for, exif_gps, find_addresses, validate_coordinates
from app.services.stats import get_stats
from app.services.report_media import save_photo

bp = Blueprint('api', __name__, url_prefix='/api')


def filtered_reports(demo_only: bool = False) -> list[Report]:
    query = db.select(Report).where(Report.saved.is_(True))
    if demo_only:
        query = query.where(Report.is_demo.is_(True))
    severity = request.args.get('severity', '')
    status = request.args.get('status', '')
    district = request.args.get('district', '')
    if severity:
        if severity not in {'NONE', 'LOW', 'MEDIUM', 'HIGH'}:
            abort(400, description='Қауіп деңгейі жарамсыз.')
        query = query.where(Report.severity == severity)
    if status:
        if status not in {'new', 'in_progress', 'repaired'}:
            abort(400, description='Мәртебе жарамсыз.')
        query = query.where(Report.status == status)
    if district:
        query = query.where(Report.district == district)
    try:
        start, end = request.args.get('from'), request.args.get('to')
        start_date = datetime.strptime(start, '%Y-%m-%d') if start else None
        end_date = datetime.strptime(end, '%Y-%m-%d') if end else None
        if start_date and end_date and start_date > end_date:
            raise ValueError()
        if start_date:
            query = query.where(Report.created_at >= start_date)
        if end_date:
            query = query.where(Report.created_at < end_date + timedelta(days=1))
    except ValueError:
        abort(400, description='Күн аралығын дұрыс көрсетіңіз.')
    return list(db.session.scalars(query.order_by(Report.created_at.desc())).all())


@bp.get('/session')
def api_session():
    import secrets
    session.setdefault('csrf_token', secrets.token_hex(24))
    return jsonify(csrf_token=session['csrf_token'])


@bp.get('/health')
def health():
    return jsonify(status='ok', ai_ready=bool(current_app.config['GEMINI_API_KEY']), model=current_app.config['GEMINI_MODEL'])


@bp.post('/assistant')
def assistant():
    require_user()
    data = request.get_json(silent=True)
    turns = data.get('turns') if isinstance(data, dict) else None
    if not isinstance(turns, list) or not 1 <= len(turns) <= 9 or len(turns) % 2 == 0:
        abort(400, description='Хабарламаны енгізіңіз.')
    contents = []
    for index, turn in enumerate(turns):
        role = 'user' if index % 2 == 0 else 'model'
        message = turn.get('text') if isinstance(turn, dict) else None
        limit = 2000 if role == 'user' else 6000
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= limit:
            abort(400, description='Хабарламаны енгізіңіз.')
        contents.append({'role': role, 'parts': [{'text': message.strip()}]})

    key = current_app.config['GEMINI_API_KEY']
    model = current_app.config['GEMINI_MODEL']
    unavailable = translate('Jolserik уақытша қолжетімсіз. Кейінірек қайталаңыз.')
    if not key or not model or not all(ch.isalnum() or ch in '.-_' for ch in model):
        return jsonify(error=unavailable), 503
    instruction = (
        'You are Jolserik, the JolScan AI road inspection assistant. Help with road damage, '
        'safe photo uploads, using the site, and understanding the illustrative repair estimate. '
        'Do not claim to access reports, submit tickets, or assess a road without evidence. '
        f'Reply in {LANGUAGES[language()]}, in plain text, concisely.'
    )
    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            headers={'x-goog-api-key': key},
            json={'systemInstruction': {'parts': [{'text': instruction}]}, 'contents': contents,
                  'generationConfig': {'maxOutputTokens': 1000}},
            timeout=(8, 45),
        )
        response.raise_for_status()
        parts = response.json()['candidates'][0]['content']['parts']
        reply = ''.join(part.get('text', '') for part in parts if not part.get('thought')).strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return jsonify(error=unavailable), 502
    if not reply:
        return jsonify(error=unavailable), 502
    return jsonify(reply=reply[:6000])


def store_analysis(image: Image.Image, gps: tuple | None, second: float | None = None) -> Report:
    clean = sanitize(image)
    result = detect(clean)
    severities = ['NONE', 'LOW', 'MEDIUM', 'HIGH']
    report = Report(summary=result['summary'], recommendation=result['recommendation'],
                    model=result['model'], inference_ms=result['inference_ms'], frame_second=second,
                    severity=max((d['severity'] for d in result['detections']), key=severities.index, default='NONE'))
    if gps:
        report.latitude, report.longitude = gps
    report.detections = [Detection(**d) for d in result['detections']]
    db.session.add(report)
    db.session.flush()
    save_photo(report, 'original', clean)
    save_photo(report, 'annotated', annotate(clean, result['detections']))
    return report


def video_frames(data: bytes) -> list[tuple[Image.Image, float]]:
    try:
        step = int(request.form.get('frame_step', current_app.config['VIDEO_FRAME_STEP']))
        if not 10 <= step <= 300:
            raise ValueError()
    except ValueError:
        abort(400, description='Кадр аралығы 10–300 болуы керек.')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'clip.mp4'
        path.write_bytes(data)
        capture = cv2.VideoCapture(str(path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if not capture.isOpened() or not math.isfinite(fps) or fps <= 0 or not math.isfinite(count) or count <= 0:
                abort(400, description='Бейне оқылмады. MP4 немесе WebM файлын қолданыңыз.')
            if count / fps > current_app.config['MAX_VIDEO_SECONDS']:
                message = translate('Бейне ұзақтығы {seconds} секундтан аспауы керек.')
                abort(400, description=message.format(seconds=current_app.config['MAX_VIDEO_SECONDS']))
            if capture.get(cv2.CAP_PROP_FRAME_WIDTH) * capture.get(cv2.CAP_PROP_FRAME_HEIGHT) > 16_000_000:
                abort(400, description='Бейне ажыратымдылығы тым үлкен.')
            frames = []
            for index in range(0, int(count), step):
                if len(frames) >= current_app.config['MAX_VIDEO_FRAMES']:
                    break
                capture.set(cv2.CAP_PROP_POS_FRAMES, index)
                success, pixels = capture.read()
                if success:
                    frames.append((Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)), round(index / fps, 2)))
            if not frames:
                abort(400, description='Бейнеде оқылатын кадр жоқ.')
            return frames
        finally:
            capture.release()


@bp.post('/detect')
def api_detect():
    require_user()
    if not current_app.config['GEMINI_API_KEY']:
        return jsonify(error=translate('Gemini API кілті қосылмаған. Баптаулар бетіндегі нұсқаулықты орындаңыз.')), 503
    upload = request.files.get('file')
    if not upload or not upload.filename:
        abort(400, description='Фото немесе бейне таңдаңыз.')
    data = upload.read()
    if not data:
        abort(400, description='Файл бос.')
    extension = Path(upload.filename).suffix.lower()
    pending = []
    try:
        if extension in {'.mp4', '.webm', '.mov'}:
            frames = video_frames(data)
            for image, second in frames:
                pending.append(store_analysis(image, None, second))
        elif extension in {'.jpg', '.jpeg', '.png', '.webp'}:
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 24_000_000:
                    abort(400, description='Сурет 24 мегапиксельден аспауы керек.')
                image.load()
                pending.append(store_analysis(image, exif_gps(image)))
        else:
            abort(400, description='JPG, PNG, WebP, MP4, MOV немесе WebM файлын таңдаңыз.')
        db.session.commit()
        session['drafts'] = (session.get('drafts', []) + [r.token for r in pending])[-60:]
        return jsonify(results=[r.as_dict() for r in pending]), 201
    except (DetectorError, RuntimeError) as exc:
        db.session.rollback()
        for report in pending:
            for kind in ('original', 'annotated'):
                (Path(current_app.config['UPLOAD_FOLDER']) / f'{report.token}_{kind}.jpg').unlink(missing_ok=True)
        return jsonify(error=translate(str(exc))), 502
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        db.session.rollback()
        return jsonify(error=translate('Файл бүлінген немесе сурет пішімі қолдау таппайды.')), 400


@bp.post('/reports')
def save_report():
    require_user()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description='JSON сұрауы қажет.')
    token = data.get('token', '')
    if token not in session.get('drafts', []):
        abort(403, description='Осы сессияның талдауын ғана сақтай аласыз.')
    report = db.session.scalar(db.select(Report).where(Report.token == token))
    if not report:
        abort(404)
    if report.saved:
        return jsonify(report=report.as_dict())
    try:
        lat, lon = validate_coordinates(data.get('latitude'), data.get('longitude'))
    except (ValueError, TypeError):
        abort(400, description='Картадан орналасқан жерді белгілеңіз.')
    report.latitude, report.longitude = lat, lon
    report.district = district_for(lat, lon)
    report.address = str(data.get('address', '')).strip()[:200]
    report.saved = True
    db.session.merge(ReportAuthor(report_id=report.id, user_id=g.user.id))
    db.session.commit()
    return jsonify(report=report.as_dict()), 201


@bp.get('/reports')
def reports():
    require_admin()
    return jsonify(reports=[r.as_dict() for r in filtered_reports()])


@bp.get('/map')
def map_data():
    records = filtered_reports(demo_only=bool(current_app.config.get('SHOWCASE_ONLY')))
    if g.user and g.user.is_admin:
        return jsonify(reports=[record.as_dict() for record in records])
    # Keep the administrative register and media private.
    points = [
        {field: getattr(report, field) for field in
         ('id', 'latitude', 'longitude', 'severity', 'status', 'address', 'district', 'is_demo')}
        for report in records
    ]
    return jsonify(reports=points)


@bp.get('/geocode')
def geocode():
    require_user()
    query = ' '.join(request.args.get('q', '').split())
    if not 3 <= len(query) <= 200:
        abort(400, description='Іздеу үшін мекенжайды енгізіңіз.')
    try:
        return jsonify(results=find_addresses(query, current_app.config['GEOCODER_URL']))
    except (requests.RequestException, ValueError):
        return jsonify(error=translate('Мекенжай іздеу уақытша қолжетімсіз. Картадан нүктені таңдаңыз.')), 502


@bp.get('/stats')
def stats():
    return jsonify(get_stats(demo_only=not (g.user and g.user.is_admin)))


@bp.patch('/reports/<int:report_id>/status')
def change_status(report_id: int):
    require_admin()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('status') not in {'new', 'in_progress', 'repaired'}:
        abort(400, description='Мәртебе жарамсыз.')
    report = db.get_or_404(Report, report_id)
    if not report.saved:
        abort(404)
    next_status = {'new': 'in_progress', 'in_progress': 'repaired'}
    target = data['status']
    if target != report.status and next_status.get(report.status) != target:
        abort(409, description='Мәртебені тек ретімен өзгертуге болады.')
    report.status = target
    db.session.commit()
    return jsonify(report=report.as_dict())


@bp.delete('/demo')
def clear_demo():
    require_admin()
    demo = db.session.scalars(db.select(Report).where(Report.is_demo.is_(True))).all()
    tokens = [r.token for r in demo]
    for report in demo:
        db.session.delete(report)
    db.session.commit()
    for token in tokens:
        for kind in ('original', 'annotated'):
            (Path(current_app.config['UPLOAD_FOLDER']) / f'{token}_{kind}.jpg').unlink(missing_ok=True)
    return jsonify(deleted=len(tokens))
