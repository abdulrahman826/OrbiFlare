"""Tests for the live NASA FIRMS API adapter (app.ingestion.firms.ingest_from_live_api).

The live HTTP call is mocked -- these tests never hit the real network -- but
they exercise the real request-construction, auth-configuration, and
CSV-parsing code paths, per the requirement to actually verify FIRMS_MAP_KEY
wiring rather than merely asserting "it should work".
"""
from __future__ import annotations

import httpx
import pytest

from app.ingestion import firms
from app.model.schemas import DataSource, Sensor

FIRMS_CSV = (
    "latitude,longitude,acq_date,acq_time,frp,bright_ti4,bright_ti5,confidence,daynight\n"
    "22.32,69.85,2025-01-15,1830,28.4,331.2,300.1,n,N\n"
    "22.33,69.86,2025-01-15,1835,,,,l,N\n"
    "not_a_lat,69.86,2025-01-15,1840,10,320,290,n,N\n"
)


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=httpx.Request("GET", "https://example.test"), response=httpx.Response(self.status_code))


class _FakeClient:
    def __init__(self, response_text: str, status_code: int = 200):
        self._response_text = response_text
        self._status_code = status_code
        self.requested_url: str | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url):
        self.requested_url = url
        return _FakeResponse(self._response_text, self._status_code)


def test_live_api_raises_without_map_key(monkeypatch):
    monkeypatch.setattr(firms.settings, "firms_map_key", "")
    with pytest.raises(RuntimeError):
        firms.ingest_from_live_api()


def test_live_api_uses_configured_map_key_and_parses_response(monkeypatch):
    monkeypatch.setattr(firms.settings, "firms_map_key", "TESTKEY123")
    fake_client = _FakeClient(FIRMS_CSV)
    monkeypatch.setattr(firms, "httpx", type("_H", (), {"Client": lambda *a, **kw: fake_client}))

    observations, quality = firms.ingest_from_live_api(bbox=(68.0, 6.0, 98.0, 37.0), day_range=1, sensor=Sensor.VIIRS)

    assert fake_client.requested_url is not None
    assert "TESTKEY123" in fake_client.requested_url
    assert "VIIRS_SNPP_NRT" in fake_client.requested_url
    assert "68.0,6.0,98.0,37.0" in fake_client.requested_url

    # 1 clean row + 1 flagged-but-accepted row (missing FRP/BT, low confidence);
    # 1 malformed row (bad latitude) rejected, not silently dropped.
    assert len(observations) == 2
    assert quality.source == DataSource.FIRMS
    assert quality.rows_received == 3
    assert quality.rows_accepted == 2
    assert quality.rows_rejected == 1
    assert all(o.source == DataSource.FIRMS for o in observations)


def test_live_api_preserves_frp_bt_confidence_daynight(monkeypatch):
    monkeypatch.setattr(firms.settings, "firms_map_key", "TESTKEY123")
    fake_client = _FakeClient(FIRMS_CSV)
    monkeypatch.setattr(firms, "httpx", type("_H", (), {"Client": lambda *a, **kw: fake_client}))

    observations, _ = firms.ingest_from_live_api()
    clean = next(o for o in observations if o.frp == 28.4)
    assert clean.brightness_temperature == 331.2
    assert clean.brightness_temperature_11 == 300.1
    assert clean.confidence == "n"
    assert clean.day_night.value == "N"
    assert clean.ingestion_time is not None


def test_live_api_flags_missing_fields_without_rejecting(monkeypatch):
    monkeypatch.setattr(firms.settings, "firms_map_key", "TESTKEY123")
    fake_client = _FakeClient(FIRMS_CSV)
    monkeypatch.setattr(firms, "httpx", type("_H", (), {"Client": lambda *a, **kw: fake_client}))

    observations, _ = firms.ingest_from_live_api()
    flagged = next(o for o in observations if o.frp is None)
    assert flagged.brightness_temperature is None
    assert "MISSING_FRP" in [q.value for q in flagged.quality_flags]
    assert "LOW_CONFIDENCE" in [q.value for q in flagged.quality_flags]


def test_live_api_propagates_http_errors(monkeypatch):
    monkeypatch.setattr(firms.settings, "firms_map_key", "TESTKEY123")
    fake_client = _FakeClient("", status_code=401)
    monkeypatch.setattr(firms, "httpx", type("_H", (), {"Client": lambda *a, **kw: fake_client}))

    with pytest.raises(httpx.HTTPStatusError):
        firms.ingest_from_live_api()


def test_live_api_key_never_leaks_into_quality_record(monkeypatch):
    monkeypatch.setattr(firms.settings, "firms_map_key", "SUPERSECRETKEY")
    fake_client = _FakeClient(FIRMS_CSV)
    monkeypatch.setattr(firms, "httpx", type("_H", (), {"Client": lambda *a, **kw: fake_client}))

    _, quality = firms.ingest_from_live_api()
    assert "SUPERSECRETKEY" not in str(quality.model_dump(mode="json"))
