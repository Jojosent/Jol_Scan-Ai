"""Размытие обнаруженных лиц локально перед отправкой в Gemini."""
import cv2
import numpy as np
from PIL import Image, ImageOps


def sanitize(image: Image.Image) -> Image.Image:
    """Применяет EXIF rotation, размывает лица и удаляет все метаданные."""
    image = ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((1920, 1920))
    pixels = np.array(image)
    classifier = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if classifier.empty():
        raise RuntimeError('Бет құпиялылығы модулі жүктелмеді. OpenCV пакетін қайта орнатыңыз.')
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    for x, y, w, h in classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)):
        margin = int(w * .15)
        x0, y0 = max(0, x-margin), max(0, y-margin)
        x1, y1 = min(pixels.shape[1], x+w+margin), min(pixels.shape[0], y+h+margin)
        pixels[y0:y1, x0:x1] = cv2.GaussianBlur(pixels[y0:y1, x0:x1], (99, 99), 35)
    return Image.fromarray(pixels)
