from app.model.schemas import QualityFlag, Sensor
from app.preprocessing.cleaning import clean_batch, deduplicate
from app.preprocessing.normalization import normalize_firms_row
from app.preprocessing.validation import validate_coordinates, validate_timestamp
from app.storage import repositories as repo


def _row(**overrides):
    row = {
        "latitude": "22.32", "longitude": "69.85", "acq_date": "2025-01-15", "acq_time": "1830",
        "frp": "28.4", "bright_ti4": "331.2", "bright_ti5": "300.1", "confidence": "n", "daynight": "N",
    }
    row.update(overrides)
    return row


def test_valid_firms_row_normalizes_cleanly():
    obs, issues = normalize_firms_row(_row(), Sensor.VIIRS)
    assert obs is not None
    assert issues == []
    assert obs.latitude == 22.32
    assert obs.frp == 28.4
    assert obs.sensor == Sensor.VIIRS


def test_malformed_row_missing_coordinates_is_rejected_not_dropped_silently():
    obs, issues = normalize_firms_row(_row(latitude="not_a_number"), Sensor.VIIRS)
    assert obs is None
    assert issues == ["missing_coordinates"]


def test_missing_frp_is_flagged_not_rejected():
    obs, issues = normalize_firms_row(_row(frp=""), Sensor.VIIRS)
    assert obs is not None
    assert QualityFlag.MISSING_FRP in obs.quality_flags


def test_out_of_range_coordinates_fail_validation():
    result = validate_coordinates(999, 69.85)
    assert not result.ok
    assert "out_of_range_coordinates" in result.reasons


def test_null_island_is_rejected():
    result = validate_coordinates(0.0, 0.0)
    assert not result.ok


def test_missing_timestamp_fails_validation():
    result = validate_timestamp(None)
    assert not result.ok


def test_duplicate_observations_are_flagged_and_excluded():
    obs, _ = normalize_firms_row(_row(), Sensor.VIIRS)
    result = clean_batch([obs, obs], rejected_rows=0)
    assert len(result.accepted) == 1
    assert result.issue_counts.get("DUPLICATE_SUSPECTED") == 1


def test_deduplicate_preserves_order_of_first_occurrence():
    obs1, _ = normalize_firms_row(_row(), Sensor.VIIRS)
    obs2, _ = normalize_firms_row(_row(latitude="10.0"), Sensor.VIIRS)
    deduped, dup_count = deduplicate([obs1, obs2, obs1])
    assert dup_count == 1
    assert [o.observation_id for o in deduped] == [obs1.observation_id, obs2.observation_id]


def test_bulk_insert_deduplicates_across_separate_ingestion_batches(db_session):
    """Two independent FIRMS pulls (e.g. two separate --live runs) that
    happen to overlap must never create duplicate rows in the database."""
    obs, _ = normalize_firms_row(_row(), Sensor.VIIRS)

    first_batch_count = repo.bulk_insert_observations(db_session, [obs])
    db_session.commit()
    assert first_batch_count == 1

    second_batch_count = repo.bulk_insert_observations(db_session, [obs])
    db_session.commit()
    assert second_batch_count == 0

    assert len(repo.list_all_observations(db_session)) == 1
