"""FinTrack - A Python package for tracking stock portfolios."""

__version__ = "1.0.0"
__author__ = "Aron Fredriksson"
__email__ = "arofre903@gmail.com"
__license__ = "MIT"

from .portfolio import FinTrack
from .yf_tools import (
    get_returns,
    get_dividends,
    get_exchange_rate,
    get_currency_from_ticker,
)
from .parsing_tools import (
    build_holding_table,
    get_portfolio,
    build_cash_table,
    generate_price_table,
    get_current_holdings_longnames,
    get_past_holdings_longnames,
)

__all__ = [
    "FinTrack",
    "get_returns",
    "get_dividends",
    "get_exchange_rate",
    "get_currency_from_ticker",
    "build_holding_table",
    "get_portfolio",
    "build_cash_table",
    "generate_price_table",
    "get_current_holdings_longnames",
    "get_past_holdings_longnames",
]
