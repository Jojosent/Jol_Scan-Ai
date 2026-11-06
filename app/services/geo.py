"""Чтение EXIF GPS до удаления метаданных и грубое определение района."""
import math
import re
from functools import lru_cache

import requests
from PIL import Image
from app.config import Config


@lru_cache(maxsize=256)
def find_addresses(query: str, endpoint: str) -> list[dict]:
    """Search addresses within greater Astana after explicit user submission."""
    response = requests.get(
        endpoint,
        params={'q': query, 'bbox': '71.15,50.95,71.85,51.4',
                'lat': 51.1694, 'lon': 71.4491, 'limit': 5},
        headers={'User-Agent': 'JolScanAI/1.0 (+https://jol-scan-ai.vercel.app)'},
        timeout=(4, 8),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get('features'), list):
        raise ValueError('Invalid geocoder response')
    matches = []
    house_numbers = re.findall(r'\b\d+[\w/-]*', query.casefold())
    for feature in payload['features'][:5]:
        try:
            lon, lat = feature['geometry']['coordinates']
            lat, lon = validate_coordinates(lat, lon)
            properties = feature['properties']
            street = properties.get('street') or properties.get('name')
            number = properties.get('housenumber')
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if not street or not (50.95 <= lat <= 51.4 and 71.15 <= lon <= 71.85):
            continue
        address = ' '.join(str(value) for value in (street, number) if value)
        exact = bool(number) and (not house_numbers or str(number).casefold() == house_numbers[-1])
        matches.append({'address': address[:200], 'latitude': lat, 'longitude': lon,
                        'exact': exact})
    return sorted(matches, key=lambda match: not match['exact'])


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
