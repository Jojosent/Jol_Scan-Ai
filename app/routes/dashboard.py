"""Панель аналитики, реестр и выгрузки с теми же фильтрами."""
import csv
import io
from flask import Blueprint, render_template, send_file
from app.routes.api import filtered_reports
from app.routes.accounts import page_login, require_admin

bp = Blueprint('dashboard', __name__)
SEVERITY = {'HIGH': 'Жоғары', 'MEDIUM': 'Орташа', 'LOW': 'Төмен', 'NONE': 'Ақау жоқ'}
STATUS = {'new': 'Жаңа', 'in_progress': 'Жөнделуде', 'repaired': 'Жөнделді'}


@bp.get('/dashboard')
def dashboard():
    return render_template('dashboard.html', page='dashboard')


@bp.get('/reports')
@bp.get('/admin')
@page_login
def reports_page():
    require_admin()
    return render_template('reports.html', page='reports')


@bp.get('/export/csv')
def export_csv():
    require_admin()
    text = io.StringIO(newline='')
    writer = csv.writer(text)
    writer.writerow(['ID', 'Күні (UTC)', 'Аудан', 'Мекенжай', 'Ендік', 'Бойлық', 'Қауіп', 'Мәртебе', 'Ақау саны', 'Басымдық', 'Демо'])
    for r in sorted(filtered_reports(), key=lambda r: r.priority, reverse=True):
        # Защита от формул при открытии CSV в Excel.
        safe_address = "'" + r.address if r.address.startswith(('=', '+', '-', '@', '\t', '\r')) else r.address
        writer.writerow([r.id, r.created_at.isoformat(), r.district, safe_address, r.latitude, r.longitude,
                         SEVERITY[r.severity], STATUS[r.status], len(r.detections), r.priority, 'Иә' if r.is_demo else 'Жоқ'])
    return send_file(io.BytesIO(text.getvalue().encode('utf-8-sig')), mimetype='text/csv; charset=utf-8', as_attachment=True, download_name='jolscan-reports.csv')


@bp.get('/export/pdf')
def export_pdf():
    require_admin()
    from app.services.report_pdf import build_pdf
    return send_file(build_pdf(filtered_reports()), mimetype='application/pdf', as_attachment=True, download_name='jolscan-report.pdf')
