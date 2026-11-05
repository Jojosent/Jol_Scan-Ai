"""Создаёт 40 явно помеченных синтетических обращений без чужих фото."""
import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from app import create_app
from app.ai.detector import annotate, classify_severity
from app.models import Report, Detection, db, utcnow

LOCATIONS = [
    ('Есіл','Қабанбай батыр даңғылы',51.122,71.447),
    ('Алматы','Тәуелсіздік даңғылы',51.166,71.49),
    ('Сарыарқа','Бейбітшілік көшесі',51.186,71.405),
    ('Байқоңыр','Абай даңғылы',51.204,71.464),
    ('Нұра','Тұран даңғылы',51.115,71.387),
]


def synthetic_road(seed: int, level: str) -> tuple[Image.Image, dict]:
    """Программная иллюстрация дорожного полотна, не AI-результат."""
    rng=random.Random(seed)
    image=Image.new('RGB',(800,500),'#66726b')
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,800,115),fill='#34484d')
    for x in range(0,800,40):
        draw.rectangle((x,115-rng.randint(20,100),x+30,115),fill='#233238')
    draw.polygon([(300,115),(500,115),(800,500),(0,500)],fill='#343a3d')
    for _ in range(6500):
        x,y=rng.randint(0,799),rng.randint(120,499)
        if abs(x-400)<((y-115)*1.05+100):
            tone=rng.randint(40,68);draw.point((x,y),fill=(tone,tone+3,tone+4))
    draw.line((300,120,25,500),fill='#b5b7a8',width=3);draw.line((500,120,775,500),fill='#b5b7a8',width=3)
    for y in (130,170,235,340):
        width=int((y-100)/14);draw.polygon([(400-width,y),(400+width,y),(403+width,y+30),(397-width,y+30)],fill='#c6ae61')
    if level=='HIGH': box=[460,450,900,830]
    elif level=='MEDIUM':box=[580,560,850,800]
    else:box=[650,600,790,740]
    y0,x0,y1,x1=box
    points=[[x0+(x1-x0)*.2,y0],[x0+(x1-x0)*.8,y0],[x1,y0+(y1-y0)*.35],[x1-(x1-x0)*.1,y1-(y1-y0)*.1],[x0+(x1-x0)*.3,y1],[x0,y0+(y1-y0)*.6]]
    draw.polygon([(x*.8,y*.5) for x,y in points],fill='#171d20',outline='#7d8070',width=4)
    draw.text((20,18),'SYNTHETIC DEMO / JolScan AI',fill='#dfd9bd')
    area=abs(sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points))))/2_000_000
    detection=dict(label='Үлгілік жол ақауы',confidence=.88,box=box,polygon=points,area_ratio=area,severity=classify_severity(area,.88))
    return image,detection


def seed_demo(with_images: bool = True) -> int:
    if db.session.scalar(db.select(Report.id).where(Report.is_demo.is_(True)).limit(1)):
        return 0
    rng=random.Random(42)
    from flask import current_app
    folder=Path(current_app.config['UPLOAD_FOLDER'])
    for index in range(40):
        district,address,lat,lon=LOCATIONS[index%5]
        level=['HIGH','MEDIUM','LOW','MEDIUM','LOW'][index%5] if index%3 else 'HIGH'
        image,detection=synthetic_road(index,level)
        report=Report(saved=True,is_demo=True,latitude=lat+rng.uniform(-.009,.009),longitude=lon+rng.uniform(-.012,.012),district=district,
                      address=f'{address}, {index+12}',severity=detection['severity'],status=['new','in_progress','new','repaired'][index%4],
                      created_at=utcnow()-timedelta(days=index%14,hours=rng.randint(0,12)),summary='Көрсетілімге арналған синтетикалық жол ақауы.',
                      recommendation='Бұл үлгілік дерек. Нақты жөндеу тапсырмасы емес.',model='synthetic-demo',inference_ms=0)
        report.detections=[Detection(**detection)]
        db.session.add(report);db.session.flush()
        if with_images:
            image.save(folder/f'{report.token}_original.jpg','JPEG',quality=85)
            annotate(image,[detection]).save(folder/f'{report.token}_annotated.jpg','JPEG',quality=85)
    db.session.commit()
    return 40


if __name__=='__main__':
    app=create_app()
    with app.app_context():
        count=seed_demo()
        print(f'Demo: {count} new reports. Existing demo records are not duplicated.')
