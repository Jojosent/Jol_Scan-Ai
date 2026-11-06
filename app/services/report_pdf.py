"""Казахский PDF-отчёт с Unicode-шрифтом, таблицей и эскизами."""
import io
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from flask import current_app
from app.models import Report, utcnow


def build_pdf(reports: list[Report]) -> io.BytesIO:
    from app.routes.dashboard import SEVERITY, STATUS
    font_path = Path(__file__).resolve().parent.parent / 'static/fonts/DejaVuSans.ttf'
    if 'DejaVu' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('DejaVu', str(font_path)))
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm,
                            topMargin=20*mm, bottomMargin=20*mm, title='JolScan AI | Жол сапасы туралы есеп', author='JolScan AI')
    styles = getSampleStyleSheet()
    title = ParagraphStyle('KKTitle', fontName='DejaVu', fontSize=24, leading=32, textColor=colors.HexColor('#18212b'), spaceAfter=12)
    heading = ParagraphStyle('KKHeading', fontName='DejaVu', fontSize=12, leading=18, spaceBefore=12, spaceAfter=10, keepWithNext=True)
    body = ParagraphStyle('KKBody', fontName='DejaVu', fontSize=8, leading=13, textColor=colors.HexColor('#495569'), spaceAfter=8)
    cell = ParagraphStyle('KKCell', parent=body, fontSize=6.7, leading=10, spaceAfter=0)
    header = ParagraphStyle('KKHeader', parent=cell, textColor=colors.white)
    top = sorted((r for r in reports if r.status != 'repaired'), key=lambda r: r.priority, reverse=True)[:20]
    story = [Paragraph('JolScan <font color="#c49b00">AI</font>', title),
             Paragraph('Астана қаласы · Жол сапасы туралы есеп', heading),
             Paragraph(f'Жасалған уақыты (UTC): {utcnow():%Y-%m-%d %H:%M}. Қолданылған сүзгілерге сәйкес сақталған өтінімдер.', body)]
    summary = [['Өтінімдер', 'Ақаулар', 'Жоғары қауіп', 'Жөнделді'],
               [str(len(reports)), str(sum(len(r.detections) for r in reports)), str(sum(r.severity == 'HIGH' for r in reports)), str(sum(r.status == 'repaired' for r in reports))]]
    summary_table = Table(summary, colWidths=[44*mm]*4)
    summary_table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'DejaVu'),('FONTSIZE',(0,0),(-1,0),8),('FONTSIZE',(0,1),(-1,1),20),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#687483')),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f2f4f6')),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story += [summary_table, Spacer(1,6*mm)]
    demos = sum(r.is_demo for r in reports)
    if demos:
        story.append(Paragraph(f'ДЕМО: {demos} үлгілік өтінім. Бұл деректер нақты жол жағдайын көрсетпейді.', body))
    story += [Paragraph('Жөндеу басымдығы · алғашқы 20 белсенді өтінім', heading),
              Paragraph('Басымдық = қауіп салмағы (1 / 3 / 5) × ақау саны × (1 + өтінім жасы / 7). Жөнделген өтінімдер бұл кезекке кірмейді.', body)]
    rows = [[Paragraph(h,header) for h in ['ID / күні','Аудан / мекенжай','Қауіп','Ақау','Мәртебе','Басымдық']]]
    for report in top:
        values = [f'#{report.id}<br/>{report.created_at:%d.%m.%Y}' + ('<br/>ДЕМО' if report.is_demo else ''),
                  escape(report.district) + '<br/>' + escape(report.address), SEVERITY[report.severity],
                  str(len(report.detections)), STATUS[report.status], str(report.priority)]
        rows.append([Paragraph(value,cell) for value in values])
    if not top:
        story.append(Paragraph('Белсенді өтінімдер жоқ.',body))
    else:
        table=Table(rows,colWidths=[23*mm,57*mm,24*mm,14*mm,33*mm,25*mm],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1b2530')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f1f4f6'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,0),2,colors.HexColor('#ffc400'))]))
        story.append(table)
    story.append(Paragraph('Фотоқұжаттар · ең жоғары басымдықтағы учаскелер',heading))
    from app.services.report_media import read_photo
    thumbs=[]
    for report in top[:6]:
        photo = read_photo(report, 'annotated')
        if photo is not None:
            picture=Image(str(photo) if isinstance(photo, Path) else photo,width=80*mm,height=50*mm,kind='proportional')
            caption=Paragraph(f'#{report.id} · {escape(report.district)} · {SEVERITY[report.severity]}' + (' · ДЕМО' if report.is_demo else ''),cell)
            thumbs.append([picture,Spacer(1,2*mm),caption])
    for index in range(0,len(thumbs),2):
        row=thumbs[index:index+2]
        if len(row)==1:row.append('')
        table=Table([row],colWidths=[88*mm,88*mm])
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
        story.append(table)
    story += [Spacer(1,5*mm),Paragraph('AI бағасы — алдын ала бағдар. Қауіп деңгейі кадрдағы жуық ауданға негізделеді. Нақты тереңдік анықталмайды. Жол қызметінің тексеруі қажет. Аудандар тікбұрышты географиялық аймақтар бойынша жуық анықталған.',body)]

    def footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#dce1e6'));canvas.line(17*mm,15*mm,193*mm,15*mm)
        canvas.setFont('DejaVu',7);canvas.setFillColor(colors.HexColor('#7b8795'))
        canvas.drawString(17*mm,10*mm,'JolScan AI · Қауіпсіз жол. Ақылды қала.')
        canvas.drawRightString(193*mm,10*mm,str(document.page));canvas.restoreState()

    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    output.seek(0)
    return output
