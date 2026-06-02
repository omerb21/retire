from pathlib import Path


def test_dockerfile_installs_wkhtmltopdf_for_cloud_pdf_generation() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "wkhtmltopdf" in dockerfile
    assert "fonts-noto-core" in dockerfile
