"""FinTrack - A Python package for tracking stock portfolios."""

__version__ = "1.1.1"
__author__ = "Aron Fredriksson"
__email__ = "arofre903@gmail.com"
__license__ = "MIT"

from .portfolio import FinTrack
from .yf_tools import (
    get_returns,
    get_dividends,
    get_exchange_rate,
    get_currency_from_ticker,
    clear_currency_cache,
)
from .parsing_tools import (
    build_holding_table,
    get_portfolio,
    build_cash_table,
    generate_price_table,
    get_current_holdings_longnames,
    get_past_holdings_longnames,
    get_cash_balance,
    get_price,
)
from .errors import (
    FinTrackError,
    ValidationError,
    DataFetchError,
    PriceError,
    DatabaseError,
    ConfigError,
)
from .config import Config
from .logger import setup_logger, get_logger

__all__ = [
    # Main class
    "FinTrack",
    # Functions
    "get_returns",
    "get_dividends",
    "get_exchange_rate",
    "get_currency_from_ticker",
    "clear_currency_cache",
    "build_holding_table",
    "get_portfolio",
    "build_cash_table",
    "generate_price_table",
    "get_current_holdings_longnames",
    "get_past_holdings_longnames",
    "get_cash_balance",
    "get_price",
    # Exceptions
    "FinTrackError",
    "ValidationError",
    "DataFetchError",
    "PriceError",
    "DatabaseError",
    "ConfigError",
    # Configuration
    "Config",
    "setup_logger",
    "get_logger",
]
