import os
from typing import Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.services.report.config import DEFAULT_HEBREW_FONT

_REGISTERED_FONT_NAME: Optional[str] = None


class FontManager:
    pass


def ensure_fonts() -> None:
    global _REGISTERED_FONT_NAME

    if _REGISTERED_FONT_NAME:
        return

    project_font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    windows_fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")

    candidates = [
        ("DejaVuSans", project_font_path),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("Arial", os.path.join(windows_fonts_dir, "arial.ttf")),
        ("ArialUnicodeMS", os.path.join(windows_fonts_dir, "ARIALUNI.TTF")),
    ]

    for font_name, font_path in candidates:
        try:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                _REGISTERED_FONT_NAME = font_name
                return
        except Exception:
            continue

    _REGISTERED_FONT_NAME = DEFAULT_HEBREW_FONT


def get_default_font() -> str:
    ensure_fonts()
    return _REGISTERED_FONT_NAME or DEFAULT_HEBREW_FONT
