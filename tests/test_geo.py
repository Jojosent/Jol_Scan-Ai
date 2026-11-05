"""GPS, привязка районов, удаление метаданных и локальное размытие."""
import io
import math
import numpy as np
import pytest
from PIL import Image
from app.services.geo import district_for, exif_gps, validate_coordinates
from app.ai.privacy import sanitize


@pytest.mark.parametrize('lat,lon,expected',[(51.12,71.45,'Есіл'),(51.12,71.38,'Нұра'),(51.20,71.47,'Байқоңыр'),(51.19,71.40,'Сарыарқа'),(51.16,71.49,'Алматы'),(0,0,'Астана шегінен тыс')])
def test_district(lat,lon,expected):
    assert district_for(lat,lon)==expected


@pytest.mark.parametrize('lat,lon',[(math.nan,71),(51,math.inf),(91,71),(51,181),(True,71)])
def test_bad_coordinates(lat,lon):
    with pytest.raises(ValueError):validate_coordinates(lat,lon)


def test_remove_exif(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        assert exif_gps(image) is None
        clean=sanitize(image)
    buffer=io.BytesIO();clean.save(buffer,'JPEG');buffer.seek(0)
    assert not Image.open(buffer).getexif()


def test_gps_conversion():
    class ImageWithGPS:
        def getexif(self):return self
        def get_ifd(self,key):return {1:'N',2:(51,10,9.84),3:'E',4:(71,26,56.76)}
    lat,lon=exif_gps(ImageWithGPS())
    assert lat==pytest.approx(51.1694)
    assert lon==pytest.approx(71.4491)


def test_detected_face_is_blurred(monkeypatch):
    class Classifier:
        def empty(self):return False
        def detectMultiScale(self,*args,**kwargs):return [(20,20,40,40)]
    monkeypatch.setattr('app.ai.privacy.cv2.CascadeClassifier',lambda path:Classifier())
    pixels=np.zeros((100,100,3),dtype=np.uint8)
    pixels[20:60:2,20:60:2]=255
    clean=np.array(sanitize(Image.fromarray(pixels)))
    assert not np.array_equal(clean[20:60,20:60],pixels[20:60,20:60])
