from datetime import date

import pytest

from app.utils.date_serializer import parse_date_flexible


def test_parse_date_flexible_accepts_yyyy_mm_dd():
    assert parse_date_flexible("2025-12-25") == date(2025, 12, 25)


def test_parse_date_flexible_accepts_dd_mm_yyyy_slash():
    assert parse_date_flexible("25/12/2025") == date(2025, 12, 25)


def test_parse_date_flexible_accepts_iso_with_time_and_z():
    assert parse_date_flexible("2025-12-25T10:11:12Z") == date(2025, 12, 25)


def test_parse_date_flexible_rejects_placeholder():
    with pytest.raises(ValueError):
        parse_date_flexible("YYYY-MM-DD")
