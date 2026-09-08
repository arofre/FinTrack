"""Yahoo Finance tools for fetching stock data."""
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

from .config import Config
from .errors import DataFetchError
from .logger import get_logger

logger = get_logger(__name__)

_CURRENCY_CACHE: Dict[str, str] = {}
_CURRENCY_CACHE_TIMESTAMPS: Dict[str, float] = {}
_CURRENCY_CACHE_LOADED = False
_EXCHANGE_RATE_CACHE: Dict[Tuple[str, str, str, str], Tuple[float, pd.Series]] = {}

CURRENCY_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30
EXCHANGE_RATE_CACHE_TTL_SECONDS = 60 * 15
YF_MAX_RETRIES = 3
YF_RETRY_BASE_DELAY_SECONDS = 0.25
YF_RETRY_JITTER_SECONDS = 0.1
CURRENCY_CACHE_FILE = Config.get_data_dir() / "ticker_currency_cache.json"


def _is_cache_entry_valid(timestamp: float, ttl_seconds: int) -> bool:
    return (time.time() - timestamp) < ttl_seconds


def _retry_yahoo_call(
    operation: Callable[[], Any],
    operation_name: str,
    max_attempts: int = YF_MAX_RETRIES,
) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as e:  # pragma: no cover - branch validated via callers
            last_error = e
            if attempt >= max_attempts:
                break
            delay = (YF_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))) + random.uniform(
                0, YF_RETRY_JITTER_SECONDS
            )
            logger.debug(
                f"{operation_name} failed on attempt {attempt}/{max_attempts}: {e}. Retrying in {delay:.2f}s"
            )
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{operation_name} failed without an exception")


def _load_currency_cache() -> None:
    global _CURRENCY_CACHE_LOADED
    if _CURRENCY_CACHE_LOADED:
        return

    _CURRENCY_CACHE_LOADED = True

    cache_path = Path(CURRENCY_CACHE_FILE)
    if not cache_path.exists():
        return

    try:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            persisted_data = json.load(cache_file)

        if not isinstance(persisted_data, dict):
            logger.debug("Currency cache file format is invalid; ignoring persisted cache")
            return

        loaded_entries = 0
        for ticker, payload in persisted_data.items():
            if not isinstance(payload, dict):
                continue
            currency = payload.get("currency")
            timestamp = payload.get("timestamp")
            if (
                isinstance(currency, str)
                and isinstance(timestamp, (int, float))
                and _is_cache_entry_valid(float(timestamp), CURRENCY_CACHE_TTL_SECONDS)
            ):
                _CURRENCY_CACHE[ticker] = currency
                _CURRENCY_CACHE_TIMESTAMPS[ticker] = float(timestamp)
                loaded_entries += 1

        logger.debug(f"Loaded {loaded_entries} ticker currency cache entries from disk")
    except Exception as e:
        logger.debug(f"Failed to load persistent currency cache: {e}")


def _persist_currency_cache() -> None:
    cache_path = Path(CURRENCY_CACHE_FILE)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    persisted_data = {}
    for ticker, currency in _CURRENCY_CACHE.items():
        timestamp = _CURRENCY_CACHE_TIMESTAMPS.get(ticker)
        if timestamp is None or not _is_cache_entry_valid(timestamp, CURRENCY_CACHE_TTL_SECONDS):
            continue
        persisted_data[ticker] = {"currency": currency, "timestamp": timestamp}

    temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as cache_file:
            json.dump(persisted_data, cache_file)
        temp_path.replace(cache_path)
    except Exception as e:
        logger.debug(f"Failed to persist currency cache: {e}")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _set_currency_cache_entry(ticker: str, currency: str) -> None:
    timestamp = time.time()
    _CURRENCY_CACHE[ticker] = currency
    _CURRENCY_CACHE_TIMESTAMPS[ticker] = timestamp
    _persist_currency_cache()


def _get_currency_from_fast_info(yf_ticker: Any) -> Optional[str]:
    try:
        fast_info = yf_ticker.fast_info
    except Exception:
        return None

    if fast_info is None:
        return None

    currency = None
    if hasattr(fast_info, "get"):
        currency = fast_info.get("currency")
    if not currency:
        currency = getattr(fast_info, "currency", None)

    if isinstance(currency, str) and currency:
        return currency
    return None


def get_returns(from_date: datetime.date, to_date: datetime.date, ticker: str) -> pd.DataFrame:
    """
    Calculate daily returns between two dates.

    Returns the percentage difference between a date's close price
    and the previous day's close price.

    Args:
        from_date: Start date
        to_date: End date
        ticker: Stock ticker symbol

    Returns:
        DataFrame of daily returns

    Raises:
        DataFetchError: If data cannot be fetched from Yahoo Finance

    Example:
        >>> returns = get_returns(date(2023, 1, 1), date(2023, 12, 31), 'AAPL')
    """
    try:
        prices = yf.download(
            ticker,
            start=from_date,
            end=to_date + timedelta(days=1),
            auto_adjust=False,
            progress=False,
        )

        if prices.empty:
            raise DataFetchError(f"No price data returned for {ticker}")

        date_range = pd.date_range(
            start=from_date, end=to_date + timedelta(days=1), freq="D"
        )
        prices = prices.reindex(date_range).ffill()
        returns = prices["Close"].pct_change().fillna(0) + 1
        return returns

    except Exception as e:
        logger.error(f"Error fetching returns for {ticker}: {e}")
        raise DataFetchError(f"Could not fetch returns for {ticker}: {str(e)}") from e


def get_dividends(from_date: datetime.date, to_date: datetime.date, ticker: str) -> pd.Series:
    """
    Get dividend payments between two dates.

    Args:
        from_date: Start date
        to_date: End date
        ticker: Stock ticker symbol

    Returns:
        Series of dividend amounts indexed by date

    Raises:
        DataFetchError: If data cannot be fetched

    Example:
        >>> divs = get_dividends(date(2023, 1, 1), date(2023, 12, 31), 'AAPL')
    """
    try:
        yf_ticker = yf.Ticker(ticker)
        dividends = yf_ticker.dividends

        if dividends is None or dividends.empty:
            return pd.Series()

        dividends.index = dividends.index.tz_localize(None)

        from_dt = datetime.combine(from_date, datetime.min.time())
        to_dt = datetime.combine(to_date, datetime.max.time())

        return dividends[(dividends.index >= from_dt) & (dividends.index <= to_dt)]

    except Exception as e:
        logger.warning(f"Could not fetch dividends for {ticker}: {e}")
        return pd.Series()


def get_exchange_rate(
    from_date: datetime.date,
    to_date: datetime.date,
    from_currency: str,
    to_currency: str,
) -> pd.Series:
    """
    Get exchange rates between two currencies for a date range.

    Args:
        from_date: Start date
        to_date: End date
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'EUR')

    Returns:
        Series of exchange rates indexed by date

    Raises:
        DataFetchError: If exchange rate data is unavailable

    Example:
        >>> rates = get_exchange_rate(date(2023, 1, 1), date(2023, 12, 31), 'USD', 'EUR')
    """
    cache_key = (
        str(from_date),
        str(to_date),
        from_currency,
        to_currency,
    )
    cache_entry = _EXCHANGE_RATE_CACHE.get(cache_key)
    if cache_entry and _is_cache_entry_valid(cache_entry[0], EXCHANGE_RATE_CACHE_TTL_SECONDS):
        logger.debug(
            f"Exchange rate cache hit for {from_currency}/{to_currency} ({from_date} -> {to_date})"
        )
        return cache_entry[1].copy()

    logger.debug(
        f"Exchange rate cache miss for {from_currency}/{to_currency} ({from_date} -> {to_date})"
    )

    start_time = perf_counter()
    try:
        exchange_ticker = f"{from_currency}{to_currency}=X"
        if from_currency == "GBp":
            exchange_ticker = f"GBP{to_currency}=X"

        rate_df = _retry_yahoo_call(
            lambda: yf.download(
                exchange_ticker,
                start=from_date,
                end=to_date + timedelta(days=1),
                auto_adjust=False,
                progress=False,
            ),
            operation_name=f"Fetching exchange rates for {exchange_ticker}",
        )

        if rate_df.empty:
            raise DataFetchError(
                f"No exchange rate data available for {exchange_ticker}"
            )

        if "Close" in rate_df.columns:
            if isinstance(rate_df["Close"], pd.DataFrame):
                rate = rate_df["Close"][exchange_ticker]
            else:
                rate = rate_df["Close"]
        else:
            rate = rate_df.iloc[:, 0]

        if from_currency == "GBp":
            rate = rate / 100

        date_range = pd.date_range(start=from_date, end=to_date, freq="D")
        rate = rate.reindex(date_range).ffill()
        rate = rate.bfill()

        _EXCHANGE_RATE_CACHE[cache_key] = (time.time(), rate.copy())
        elapsed = perf_counter() - start_time
        logger.debug(
            f"Fetched exchange rates for {exchange_ticker} in {elapsed:.3f}s ({len(rate)} rows)"
        )
        return rate

    except Exception as e:
        logger.error(f"Error fetching exchange rates for {from_currency}/{to_currency}: {e}")
        raise DataFetchError(
            f"Could not fetch exchange rates for {from_currency}/{to_currency}: {str(e)}"
        ) from e


def get_currency_from_ticker(ticker: str) -> str:
    """
    Get the currency a stock is traded in.

    Uses caching to avoid repeated API calls.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Currency code (e.g., 'USD')

    Raises:
        DataFetchError: If currency information is unavailable

    Example:
        >>> currency = get_currency_from_ticker('AAPL')
        >>> currency
        'USD'
    """
    _load_currency_cache()

    if ticker in _CURRENCY_CACHE:
        timestamp = _CURRENCY_CACHE_TIMESTAMPS.get(ticker)
        if timestamp is not None and _is_cache_entry_valid(timestamp, CURRENCY_CACHE_TTL_SECONDS):
            logger.debug(f"Ticker currency cache hit for {ticker}")
            return _CURRENCY_CACHE[ticker]
        _CURRENCY_CACHE.pop(ticker, None)
        _CURRENCY_CACHE_TIMESTAMPS.pop(ticker, None)
        _persist_currency_cache()

    logger.debug(f"Ticker currency cache miss for {ticker}")

    start_time = perf_counter()
    try:
        yf_ticker = yf.Ticker(ticker)
        currency = _get_currency_from_fast_info(yf_ticker)

        if not currency:
            info = _retry_yahoo_call(
                lambda: yf_ticker.info,
                operation_name=f"Fetching ticker info for {ticker}",
            )
            if isinstance(info, dict):
                currency = info.get("currency")

        if not currency:
            raise DataFetchError(f"No currency information for {ticker}")

        _set_currency_cache_entry(ticker, currency)
        elapsed = perf_counter() - start_time
        logger.debug(f"Fetched ticker currency for {ticker} in {elapsed:.3f}s using Yahoo metadata")
        return currency

    except Exception as e:
        logger.error(f"Error fetching currency for {ticker}: {e}")
        raise DataFetchError(f"Could not determine currency for {ticker}: {str(e)}") from e


def clear_currency_cache() -> None:
    """
    Clear the currency lookup cache.

    Useful for testing or when ticker currency mappings may have changed.

    Example:
        >>> clear_currency_cache()
    """
    global _CURRENCY_CACHE_LOADED
    _CURRENCY_CACHE.clear()
    _CURRENCY_CACHE_TIMESTAMPS.clear()
    _EXCHANGE_RATE_CACHE.clear()
    _CURRENCY_CACHE_LOADED = False
    Path(CURRENCY_CACHE_FILE).unlink(missing_ok=True)
    logger.debug("Currency cache cleared")
