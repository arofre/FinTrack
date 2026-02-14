"""Yahoo Finance tools for fetching stock data."""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from .errors import DataFetchError
from .logger import get_logger

logger = get_logger(__name__)

_CURRENCY_CACHE = {}


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
    try:
        exchange_ticker = f"{from_currency}{to_currency}=X"
        if from_currency == "GBp":
            exchange_ticker = f"GBP{to_currency}=X"

        rate_df = yf.download(
            exchange_ticker,
            start=from_date,
            end=to_date + timedelta(days=1),
            auto_adjust=False,
            progress=False,
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
    if ticker in _CURRENCY_CACHE:
        return _CURRENCY_CACHE[ticker]

    try:
        yf_ticker = yf.Ticker(ticker)
        currency = yf_ticker.info.get("currency")

        if not currency:
            raise DataFetchError(f"No currency information for {ticker}")

        _CURRENCY_CACHE[ticker] = currency
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
    global _CURRENCY_CACHE
    _CURRENCY_CACHE.clear()
    logger.debug("Currency cache cleared")
