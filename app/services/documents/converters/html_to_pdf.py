"""
המרת HTML ל-PDF באמצעות wkhtmltopdf
"""

import logging
import subprocess
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class _DocumentHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, object]] = []
        self._text_parts: list[str] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._in_ignored_tag = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"style", "script"}:
            self._in_ignored_tag = True
            return
        if tag == "table":
            self._flush_text()
            self._table = []
            return
        if tag == "tr" and self._table is not None:
            self._row = []
            return
        if tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []
            return
        if tag in {"br", "hr"}:
            self._append_text("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"style", "script"}:
            self._in_ignored_tag = False
            return
        if tag in {"td", "th"} and self._cell_parts is not None:
            cell = " ".join("".join(self._cell_parts).split())
            if self._row is not None:
                self._row.append(cell)
            self._cell_parts = None
            return
        if tag == "tr" and self._row is not None:
            if any(cell for cell in self._row) and self._table is not None:
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
        if self._in_ignored_tag:
            return
        if self._cell_parts is not None:
            self._cell_parts.append(data)
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
            story.append(Paragraph(escape(str(value)), base_style))
            story.append(Spacer(1, 6))
            continue

        table_rows = value if isinstance(value, list) else []
        if not table_rows:
            continue
        column_count = max(len(row) for row in table_rows)
        normalized_rows = [
            [
                Paragraph(escape(str(cell)), base_style)
                for cell in (row + [""] * (column_count - len(row)))
            ]
            for row in table_rows
        ]
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
