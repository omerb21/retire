from pathlib import Path


def test_cloud_pdf_generation_does_not_depend_on_unavailable_wkhtmltopdf_package() -> (
    None
):
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    converter = Path("app/services/documents/converters/html_to_pdf.py").read_text(
        encoding="utf-8"
    )

    assert "wkhtmltopdf \\" not in dockerfile
    assert "fonts-noto-core" in dockerfile
    assert "_html_to_pdf_reportlab" in converter
