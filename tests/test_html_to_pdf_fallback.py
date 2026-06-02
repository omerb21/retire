import importlib
from pathlib import Path


def test_html_to_pdf_creates_pdf_when_wkhtmltopdf_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    html_path = tmp_path / "sample.html"
    pdf_path = tmp_path / "sample.pdf"
    html_path.write_text(
        """
        <html dir="rtl" lang="he">
          <body>
            <h1>Grants appendix</h1>
            <table>
              <tr><th>Employer</th><th>Amount</th></tr>
              <tr><td>First employer</td><td>0</td></tr>
            </table>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    converter_module = importlib.import_module(
        "app.services.documents.converters.html_to_pdf"
    )
    monkeypatch.setattr(converter_module, "find_wkhtmltopdf", lambda: None)

    result = converter_module.html_to_pdf(html_path, pdf_path)

    assert result == pdf_path
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_reportlab_fallback_shapes_hebrew_for_visual_rtl_display() -> None:
    converter_module = importlib.import_module(
        "app.services.documents.converters.html_to_pdf"
    )

    assert converter_module._shape_text("שלום") == "םולש"
