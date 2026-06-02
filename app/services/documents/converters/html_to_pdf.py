"""
המרת HTML ל-PDF באמצעות wkhtmltopdf
"""

import logging
import re
import subprocess
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _attrs_to_dict(attrs: list[tuple[str, Optional[str]]]) -> dict[str, str]:
    return {name.lower(): value or "" for name, value in attrs}


def _extract_style_value(style: str, property_name: str) -> str | None:
    match = re.search(
        rf"(?:^|;)\s*{re.escape(property_name)}\s*:\s*([^;]+)",
        style or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip()


def _extract_first_css_color(css: str, selector: str, property_name: str) -> str | None:
    match = re.search(
        rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}",
        css or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return _extract_style_value(match.group("body"), property_name)


class _DocumentHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, object]] = []
        self._text_parts: list[str] = []
        self._style_parts: list[str] = []
        self._table: list[dict[str, Any]] | None = None
        self._row: dict[str, Any] | None = None
        self._cell: dict[str, Any] | None = None
        self._in_style_tag = False
        self._in_script_tag = False
        self.is_rtl = False
        self.stylesheet = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attr_map = _attrs_to_dict(attrs)
        if tag == "html" and attr_map.get("dir", "").lower() == "rtl":
            self.is_rtl = True
            return
        if tag == "style":
            self._in_style_tag = True
            return
        if tag == "script":
            self._in_script_tag = True
            return
        if tag == "table":
            self._flush_text()
            self._table = []
            return
        if tag == "tr" and self._table is not None:
            self._row = {
                "cells": [],
                "class": attr_map.get("class", ""),
                "style": attr_map.get("style", ""),
            }
            return
        if tag in {"td", "th"} and self._row is not None:
            self._cell = {
                "text_parts": [],
                "style": attr_map.get("style", ""),
                "is_header": tag == "th",
            }
            return
        if tag in {"br", "hr"}:
            self._append_text("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style":
            self._in_style_tag = False
            self.stylesheet += "\n".join(self._style_parts)
            self._style_parts = []
            return
        if tag == "script":
            self._in_script_tag = False
            return
        if tag in {"td", "th"} and self._cell is not None:
            cell = {
                "text": " ".join("".join(self._cell["text_parts"]).split()),
                "style": self._cell["style"],
                "is_header": self._cell["is_header"],
            }
            if self._row is not None:
                self._row["cells"].append(cell)
            self._cell = None
            return
        if tag == "tr" and self._row is not None:
            if (
                any(cell.get("text") for cell in self._row["cells"])
                and self._table is not None
            ):
                self._table.append(self._row)
            self._row = None
            return
        if tag == "table":
            if self._table:
                self.blocks.append(("table", self._table))
            self._table = None
            return
        if tag in {"h1", "h2", "h3", "p", "div", "li"}:
            self._flush_text()

    def handle_data(self, data: str) -> None:
        if self._in_style_tag:
            self._style_parts.append(data)
            return
        if self._in_script_tag:
            return
        if self._cell is not None:
            self._cell["text_parts"].append(data)
            return
        if self._table is None:
            self._append_text(data)

    def _append_text(self, value: str) -> None:
        if value:
            self._text_parts.append(value)

    def _flush_text(self) -> None:
        text = " ".join("".join(self._text_parts).split())
        if text:
            self.blocks.append(("text", text))
        self._text_parts = []

    def close(self) -> None:
        super().close()
        self._flush_text()


def _parse_margin(value: str) -> float:
    raw = str(value or "").strip().lower()
    try:
        if raw.endswith("mm"):
            return float(raw[:-2]) * 72 / 25.4
        if raw.endswith("cm"):
            return float(raw[:-2]) * 72 / 2.54
        if raw.endswith("in"):
            return float(raw[:-2]) * 72
        return float(raw)
    except (TypeError, ValueError):
        return 28.35


def _shape_text(value: object) -> str:
    text = str(value or "")
    try:
        from bidi.algorithm import get_display

        return get_display(text)
    except Exception:
        return text


def _to_reportlab_color(value: str | None, default):
    from reportlab.lib import colors

    if not value:
        return default
    raw = value.strip().lower()
    if raw == "white":
        return colors.white
    if raw == "black":
        return colors.black
    try:
        return colors.HexColor(raw)
    except Exception:
        return default


def _paragraph_for_cell(
    value: object,
    base_style,
    *,
    is_header: bool = False,
    text_color=None,
    bold: bool = False,
):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    style = base_style
    if is_header or text_color or bold:
        style = ParagraphStyle(
            f"{base_style.name}_{hash((str(value), is_header, str(text_color), bold))}",
            parent=base_style,
            textColor=text_color or (colors.white if is_header else colors.black),
        )
    return Paragraph(escape(_shape_text(value)), style)


def _register_pdf_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("RetireUnicode", str(path)))
            return "RetireUnicode"
        except Exception:
            continue
    return "Helvetica"


def _html_to_pdf_reportlab(
    html_path: Path,
    pdf_path: Path,
    page_size: str,
    margin_top: str,
    margin_right: str,
    margin_bottom: str,
    margin_left: str,
) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    parser = _DocumentHTMLParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    parser.close()

    page = letter if str(page_size).lower() == "letter" else A4
    font_name = _register_pdf_font()
    header_background = _to_reportlab_color(
        _extract_first_css_color(parser.stylesheet, "th", "background-color"),
        colors.HexColor("#3498db"),
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=page,
        rightMargin=_parse_margin(margin_right),
        leftMargin=_parse_margin(margin_left),
        topMargin=_parse_margin(margin_top),
        bottomMargin=_parse_margin(margin_bottom),
    )

    styles = getSampleStyleSheet()
    base_style = ParagraphStyle(
        "RetireFallbackBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT,
    )
    story = []

    for block_type, value in parser.blocks:
        if block_type == "text":
            story.append(Paragraph(escape(_shape_text(value)), base_style))
            story.append(Spacer(1, 6))
            continue

        table_rows = value if isinstance(value, list) else []
        if not table_rows:
            continue
        column_count = max(len(row.get("cells", [])) for row in table_rows)
        normalized_rows = []
        row_styles = []
        for row_index, row in enumerate(table_rows):
            cells = list(row.get("cells", []))
            cells = cells + [
                {"text": "", "style": "", "is_header": False}
                for _ in range(column_count - len(cells))
            ]
            if parser.is_rtl:
                cells.reverse()

            row_style = row.get("style", "")
            row_class = row.get("class", "")
            row_color = _extract_style_value(row_style, "color")
            is_header_row = any(cell.get("is_header") for cell in cells)
            is_total_row = "total-row" in row_class

            normalized_rows.append(
                [
                    _paragraph_for_cell(
                        cell.get("text", ""),
                        base_style,
                        is_header=bool(cell.get("is_header")),
                        text_color=_to_reportlab_color(
                            _extract_style_value(cell.get("style", ""), "color")
                            or row_color,
                            None,
                        ),
                        bold=(
                            is_total_row
                            or "bold"
                            in str(
                                _extract_style_value(
                                    cell.get("style", ""), "font-weight"
                                )
                                or ""
                            ).lower()
                        ),
                    )
                    for cell in cells
                ]
            )

            row_background = _extract_style_value(row_style, "background-color")
            if is_header_row:
                row_styles.extend(
                    [
                        (
                            "BACKGROUND",
                            (0, row_index),
                            (-1, row_index),
                            header_background,
                        ),
                        ("TEXTCOLOR", (0, row_index), (-1, row_index), colors.white),
                    ]
                )
            if is_total_row:
                row_styles.extend(
                    [
                        (
                            "BACKGROUND",
                            (0, row_index),
                            (-1, row_index),
                            colors.HexColor("#ecf0f1"),
                        ),
                        ("FONTNAME", (0, row_index), (-1, row_index), font_name),
                    ]
                )
            if row_background:
                row_styles.append(
                    (
                        "BACKGROUND",
                        (0, row_index),
                        (-1, row_index),
                        _to_reportlab_color(row_background, colors.white),
                    )
                )
            if row_color:
                row_styles.append(
                    (
                        "TEXTCOLOR",
                        (0, row_index),
                        (-1, row_index),
                        _to_reportlab_color(row_color, colors.black),
                    )
                )

        table = Table(normalized_rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
                + row_styles
            )
        )
        story.append(table)
        story.append(Spacer(1, 8))

    if not story:
        story.append(Paragraph("PDF document", base_style))

    doc.build(story)
    logger.info("PDF created with reportlab fallback: %s", pdf_path)
    return pdf_path


def _to_wkhtmltopdf_input_url(path: Path) -> str:
    resolved = path.resolve()
    raw = str(resolved).replace("\\", "/")
    if len(raw) >= 3 and raw[1] == ":" and raw[2] == "/":
        return f"file:///{raw}"
    return raw


def find_wkhtmltopdf() -> Optional[str]:
    """
    מחפש את wkhtmltopdf במיקומים נפוצים

    Returns:
        נתיב ל-wkhtmltopdf או None אם לא נמצא
    """
    wkhtmltopdf_paths = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        "wkhtmltopdf",  # אם זמין ב-PATH
    ]

    for path in wkhtmltopdf_paths:
        try:
            subprocess.run(
                [path, "--version"], capture_output=True, check=True, timeout=5
            )
            logger.info(f"✅ Found wkhtmltopdf at: {path}")
            return path
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            continue

    logger.error("❌ wkhtmltopdf not found in any common location")
    return None


def html_to_pdf(
    html_path: Path,
    pdf_path: Path,
    page_size: str = "A4",
    margin_top: str = "10mm",
    margin_right: str = "10mm",
    margin_bottom: str = "10mm",
    margin_left: str = "10mm",
) -> Path:
    """
    ממיר קובץ HTML ל-PDF באמצעות wkhtmltopdf

    Args:
        html_path: נתיב לקובץ HTML
        pdf_path: נתיב לקובץ PDF היעד
        page_size: גודל עמוד (ברירת מחדל: A4)
        margin_top: שוליים עליונים
        margin_right: שוליים ימניים
        margin_bottom: שוליים תחתונים
        margin_left: שוליים שמאליים

    Returns:
        נתיב לקובץ PDF שנוצר

    Raises:
        RuntimeError: אם wkhtmltopdf לא נמצא או ההמרה נכשלה
    """
    wkhtmltopdf_path = find_wkhtmltopdf()

    if not wkhtmltopdf_path:
        logger.warning("wkhtmltopdf not found; using reportlab PDF fallback")
        return _html_to_pdf_reportlab(
            html_path,
            pdf_path,
            page_size,
            margin_top,
            margin_right,
            margin_bottom,
            margin_left,
        )

    html_input = _to_wkhtmltopdf_input_url(html_path)

    cmd = [
        wkhtmltopdf_path,
        "--enable-local-file-access",
        "--encoding",
        "UTF-8",
        "--page-size",
        page_size,
        "--margin-top",
        margin_top,
        "--margin-right",
        margin_right,
        "--margin-bottom",
        margin_bottom,
        "--margin-left",
        margin_left,
        html_input,
        str(pdf_path),
    ]

    logger.info(f"🔄 Converting HTML to PDF: {html_path} -> {pdf_path}")
    logger.debug("wkhtmltopdf command: %s", cmd)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf failed: {result.stderr.strip()}")

        logger.info(f"✅ PDF created successfully: {pdf_path}")
        return pdf_path

    except subprocess.TimeoutExpired:
        logger.warning(
            "wkhtmltopdf timed out after 30 seconds; using reportlab fallback"
        )
        return _html_to_pdf_reportlab(
            html_path,
            pdf_path,
            page_size,
            margin_top,
            margin_right,
            margin_bottom,
            margin_left,
        )
    except Exception as e:
        logger.warning("wkhtmltopdf conversion failed; using reportlab fallback: %s", e)
        return _html_to_pdf_reportlab(
            html_path,
            pdf_path,
            page_size,
            margin_top,
            margin_right,
            margin_bottom,
            margin_left,
        )
