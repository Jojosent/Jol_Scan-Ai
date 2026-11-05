"""Пользовательский язык интерфейса и общий каталог сервера и браузера."""
from pathlib import Path

from flask import has_request_context, request

LANGUAGES = {'kk': 'Kazakh', 'ru': 'Russian', 'en': 'English'}
CATALOG = {language: {} for language in LANGUAGES}
for line in (Path(__file__).parent / 'i18n/ui.txt').read_text(encoding='utf-8').splitlines():
    if line.strip():
        source, russian, english, *kazakh = line.split('|')
        if kazakh:
            CATALOG['kk'][source] = kazakh[0]
        CATALOG['ru'][source] = russian
        CATALOG['en'][source] = english


def language() -> str:
    selected = request.cookies.get('jolscan_language', 'kk') if has_request_context() else 'kk'
    return selected if selected in LANGUAGES else 'kk'


def translate(source: str) -> str:
    return CATALOG[language()].get(source, source)
