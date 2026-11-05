"""Чтение EXIF GPS до удаления метаданных и грубое определение района."""
import math
from PIL import Image
from app.config import Config


def validate_coordinates(lat: object, lon: object) -> tuple[float, float]:
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError('Координаттарды дұрыс көрсетіңіз.')
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Координаттарды дұрыс көрсетіңіз.')
    return lat, lon


def district_for(lat: float, lon: float) -> str:
    for name, (south, west, north, east) in Config.DISTRICT_BOXES:
        if south <= lat <= north and west <= lon <= east:
            return name
    return 'Астана шегінен тыс'


def exif_gps(image: Image.Image) -> tuple[float, float] | None:
    try:
        gps = image.getexif().get_ifd(34853)
        def decimal(values: tuple, ref: str) -> float:
            value = float(values[0]) + float(values[1]) / 60 + float(values[2]) / 3600
            return -value if ref in ('S', 'W') else value
        if gps and all(k in gps for k in (1, 2, 3, 4)):
            return validate_coordinates(decimal(gps[2], gps[1]), decimal(gps[4], gps[3]))
    except (ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError):
        pass
    return None
