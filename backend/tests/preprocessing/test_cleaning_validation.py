from datetime import datetime

from app.preprocessing.validation import validate_coordinates, validate_thermal_fields, validate_timestamp


def test_valid_coordinates_pass():
    assert validate_coordinates(22.3, 69.8).ok


def test_valid_timestamp_passes():
    assert validate_timestamp(datetime(2025, 6, 1)).ok


def test_implausible_future_timestamp_fails():
    assert not validate_timestamp(datetime(2099, 1, 1)).ok


def test_thermal_fields_missing_are_flagged_but_not_fatal():
    result = validate_thermal_fields(None, None)
    assert result.ok  # still usable -- coordinates/time can anchor an event
    assert "missing_frp" in result.reasons
    assert "missing_bt" in result.reasons


def test_thermal_fields_out_of_plausible_range_flagged():
    result = validate_thermal_fields(frp=99999, bt=1000)
    assert "frp_out_of_plausible_range" in result.reasons
    assert "bt_out_of_plausible_range" in result.reasons
