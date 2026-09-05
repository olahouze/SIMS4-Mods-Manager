from datetime import datetime
from src.utils.version_utils import parse_flexible_date, normalize_version


def test_parse_flexible_date():
    # ISO formats
    d1 = parse_flexible_date("2024-05-18T14:30:00")
    assert d1 == datetime(2024, 5, 18, 14, 30, 0)

    # European format
    d2 = parse_flexible_date("18/05/2024")
    assert d2 == datetime(2024, 5, 18)

    # US text formats
    d3 = parse_flexible_date("May 18, 2024")
    assert d3 == datetime(2024, 5, 18)

    # Invalid / empty
    assert parse_flexible_date(None) is None
    assert parse_flexible_date("") is None
    assert parse_flexible_date("not a date") is None


def test_normalize_version():
    assert normalize_version("v1.2.3") == "1.2.3"
    assert normalize_version("ver. 2.0.1") == "2.0.1"
    assert normalize_version("version 3.4 (Latest)") == "3.4"
    assert normalize_version("4.5.1") == "4.5.1"
    assert normalize_version("") == ""
    assert normalize_version(None) == ""
