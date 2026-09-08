"""Tests for Yahoo Finance helper utilities."""
from datetime import date

import pandas as pd
import pytest

from src.FinTrack import yf_tools
from src.FinTrack.errors import DataFetchError


@pytest.fixture
def isolated_caches(monkeypatch, tmp_path):
    """Isolate caches and persistence for yf_tools tests."""
    monkeypatch.setattr(yf_tools, "CURRENCY_CACHE_FILE", tmp_path / "ticker_currency_cache.json")
    yf_tools.clear_currency_cache()
    monkeypatch.setattr(yf_tools, "CURRENCY_CACHE_TTL_SECONDS", 3600)
    monkeypatch.setattr(yf_tools, "EXCHANGE_RATE_CACHE_TTL_SECONDS", 3600)
    yield
    yf_tools.clear_currency_cache()


def test_get_currency_from_ticker_prefers_fast_info(monkeypatch, isolated_caches):
    """Currency lookup should use fast_info before info."""

    class FakeTicker:
        fast_info = {"currency": "USD"}

        @property
        def info(self):
            raise AssertionError("info should not be fetched when fast_info has currency")

    monkeypatch.setattr(yf_tools.yf, "Ticker", lambda _: FakeTicker())
    assert yf_tools.get_currency_from_ticker("AAPL") == "USD"


def test_get_currency_from_ticker_falls_back_to_info(monkeypatch, isolated_caches):
    """Currency lookup should fall back to info when fast_info has no currency."""

    class FakeTicker:
        fast_info = {}

        @property
        def info(self):
            return {"currency": "SEK"}

    monkeypatch.setattr(yf_tools.yf, "Ticker", lambda _: FakeTicker())
    assert yf_tools.get_currency_from_ticker("VOLCAR-B.ST") == "SEK"


def test_get_currency_from_ticker_uses_persisted_cache(monkeypatch, isolated_caches):
    """Persisted currency cache should be reused after in-memory cache is reset."""

    class FakeTicker:
        fast_info = {"currency": "EUR"}
        info = {"currency": "EUR"}

    monkeypatch.setattr(yf_tools.yf, "Ticker", lambda _: FakeTicker())
    assert yf_tools.get_currency_from_ticker("SAP.DE") == "EUR"

    # Simulate process restart by clearing in-memory caches only.
    yf_tools._CURRENCY_CACHE.clear()
    yf_tools._CURRENCY_CACHE_TIMESTAMPS.clear()
    yf_tools._CURRENCY_CACHE_LOADED = False

    def fail_if_called(_):
        raise AssertionError("Ticker lookup should use persisted cache")

    monkeypatch.setattr(yf_tools.yf, "Ticker", fail_if_called)
    assert yf_tools.get_currency_from_ticker("SAP.DE") == "EUR"


def test_get_exchange_rate_uses_ttl_cache_and_retry(monkeypatch, isolated_caches):
    """Exchange rate lookups should retry transient failures and cache results."""
    call_count = {"count": 0}

    def fake_download(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("temporary network failure")
        idx = pd.to_datetime(["2024-01-01", "2024-01-03"])
        return pd.DataFrame({"Close": [10.0, 12.0]}, index=idx)

    monkeypatch.setattr(yf_tools.yf, "download", fake_download)
    monkeypatch.setattr(yf_tools.time, "sleep", lambda _: None)
    monkeypatch.setattr(yf_tools.random, "uniform", lambda _a, _b: 0.0)

    result_1 = yf_tools.get_exchange_rate(date(2024, 1, 1), date(2024, 1, 3), "USD", "SEK")
    result_2 = yf_tools.get_exchange_rate(date(2024, 1, 1), date(2024, 1, 3), "USD", "SEK")

    assert call_count["count"] == 2
    assert result_1.equals(result_2)
    assert len(result_1) == 3


def test_get_currency_from_ticker_raises_data_fetch_error(monkeypatch, isolated_caches):
    """Missing currency should preserve DataFetchError contract."""

    class FakeTicker:
        fast_info = {}
        info = {}

    monkeypatch.setattr(yf_tools.yf, "Ticker", lambda _: FakeTicker())

    with pytest.raises(DataFetchError) as exc:
        yf_tools.get_currency_from_ticker("UNKNOWN")

    assert "Could not determine currency for UNKNOWN" in str(exc.value)
