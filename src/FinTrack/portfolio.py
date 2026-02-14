"""Main FinTrack portfolio tracker class."""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from .config import Config
from .errors import FinTrackError, ValidationError, DataFetchError
from .logger import get_logger
from .parsing_tools import (
    build_holding_table,
    build_cash_table,
    generate_price_table,
    get_current_holdings_longnames,
    get_past_holdings_longnames,
    get_portfolio,
    get_cash_balance,
    get_price,
)
from .validation import validate_initial_cash, validate_currency

logger = get_logger(__name__)


class FinTrack:
    """
    Portfolio tracker for managing stock investments.

    Tracks stock holdings, prices, and cash balances with support for
    multiple currencies and automatic dividend handling.

    Attributes:
        initial_cash (int): Starting cash amount in portfolio currency
        currency (str): Base currency code (e.g., 'USD', 'EUR', 'SEK')
        csv_file (str): Path to CSV file with transactions
        user_id (Optional[str]): User identifier for multi-user setups

    Example:
        >>> portfolio = FinTrack(
        ...     initial_cash=150000,
        ...     currency="SEK",
        ...     csv_file="transactions.csv"
        ... )
        >>> portfolio.update_portfolio()
        >>> holdings = portfolio.get_current_holdings()
    """

    def __init__(
        self,
        initial_cash: int,
        currency: str,
        csv_file: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the portfolio tracker.

        Args:
            initial_cash: Starting cash amount
            currency: Base currency code (e.g., 'USD', 'EUR')
            csv_file: Path to transactions CSV file
            user_id: Optional user identifier for multi-user setups

        Raises:
            FileNotFoundError: If csv_file does not exist
            ValidationError: If parameters are invalid

        Example:
            >>> portfolio = FinTrack(150000, "USD", "transactions.csv")
        """
        logger.info(f"Initializing FinTrack portfolio with {initial_cash} {currency}")

        validate_initial_cash(initial_cash)
        validate_currency(currency)

        self.initial_cash = initial_cash
        self.currency = currency
        self.csv_file = csv_file
        self.user_id = user_id or "default"

        logger.debug(f"Portfolio config: initial_cash={initial_cash}, currency={currency}, csv_file={csv_file}")

        try:
            build_holding_table(csv_file, self.user_id)
            generate_price_table(currency, csv_file, self.user_id)
            build_cash_table(csv_file, initial_cash, currency, self.user_id)
            logger.info("Portfolio initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize portfolio: {e}")
            raise FinTrackError(f"Portfolio initialization failed: {str(e)}") from e

    def update_portfolio(self) -> None:
        """
        Update portfolio with latest data from Yahoo Finance.

        Fetches current stock prices, processes new transactions,
        and calculates dividend payments.

        Raises:
            FinTrackError: If update operations fail

        Example:
            >>> portfolio.update_portfolio()
        """
        logger.info("Updating portfolio")

        try:
            build_holding_table(self.csv_file, self.user_id)
            generate_price_table(self.currency, self.csv_file, self.user_id)
            build_cash_table(self.csv_file, self.initial_cash, self.currency, self.user_id)
            logger.info("Portfolio update completed successfully")
        except Exception as e:
            logger.error(f"Portfolio update failed: {e}")
            raise FinTrackError(f"Portfolio update failed: {str(e)}") from e

    def get_current_holdings(self) -> List[str]:
        """
        Get current stock holdings with company names.

        Returns:
            List of long company names currently held

        Example:
            >>> holdings = portfolio.get_current_holdings()
            >>> holdings
            ['Apple Inc.', 'Microsoft Corporation', 'Tesla, Inc.']
        """
        logger.debug("Retrieving current holdings")
        return get_current_holdings_longnames(self.user_id)

    def get_past_holdings(self) -> List[str]:
        """
        Get all holdings ever owned with company names.

        Includes positions that have been completely sold.

        Returns:
            List of long company names ever held

        Example:
            >>> holdings = portfolio.get_past_holdings()
        """
        logger.debug("Retrieving past holdings")
        return get_past_holdings_longnames(self.user_id)

    def get_portfolio_cash(self, target_date: date) -> Optional[float]:
        """
        Get cash balance on a specific date.

        Args:
            target_date: Date to check cash balance

        Returns:
            Cash balance in base currency, or None if not found

        Raises:
            ValueError: If date is before portfolio start

        Example:
            >>> cash = portfolio.get_portfolio_cash(date(2023, 6, 15))
            >>> cash
            145250.75
        """
        logger.debug(f"Retrieving cash balance for {target_date}")
        return get_cash_balance(target_date, self.user_id)

    def get_portfolio_value(
        self, from_date: date, to_date: date
    ) -> Dict[date, float]:
        """
        Calculate portfolio value for each day in date range.

        Portfolio value = (shares held × price per share) + cash balance

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Dict mapping dates to portfolio values in base currency

        Example:
            >>> values = portfolio.get_portfolio_value(
            ...     date(2023, 1, 1),
            ...     date(2023, 12, 31)
            ... )
            >>> for date_key, value in sorted(values.items()):
            ...     print(f"{date_key}: {value:,.2f}")
        """
        logger.info(f"Calculating portfolio values from {from_date} to {to_date}")

        date_range = pd.date_range(from_date, to_date)
        range_value = {}

        for date_val in date_range:
            target_date = date_val.date()
            portfolio = get_portfolio(target_date, self.user_id)
            value = 0

            if portfolio:
                for ticker in portfolio.keys():
                    amount = portfolio[ticker]
                    try:
                        price = get_price(ticker, target_date, self.user_id)
                        if price is not None:
                            value += amount * price
                    except Exception as e:
                        logger.warning(f"Could not get price for {ticker} on {target_date}: {e}")

            cash = get_cash_balance(target_date, self.user_id)
            if cash is not None:
                value += cash

            range_value[target_date] = value

        logger.info(f"Calculated portfolio values for {len(range_value)} dates")
        return range_value

    def get_index_returns(
        self, ticker: str, start_date: date, end_date: date
    ) -> List[float]:
        """
        Get daily returns for a benchmark index.

        Returns are calculated as (price - initial_price) / initial_price.

        Args:
            ticker: Yahoo Finance ticker (e.g., '^GSPC' for S&P 500)
            start_date: Start date
            end_date: End date

        Returns:
            List of daily returns (as decimals, e.g., 0.02 = 2%)

        Raises:
            DataFetchError: If index data cannot be fetched

        Example:
            >>> returns = portfolio.get_index_returns(
            ...     '^GSPC',
            ...     date(2023, 1, 1),
            ...     date(2023, 12, 31)
            ... )
            >>> print(f"S&P 500 final return: {returns[-1]:.2%}")
        """
        logger.info(f"Fetching index returns for {ticker} from {start_date} to {end_date}")

        try:
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date + timedelta(days=1),
                progress=False,
            )

            if df.empty:
                raise DataFetchError(f"No data available for {ticker}")

            df = df.asfreq("D")
            df["Close"] = df["Close"].ffill()

            prices = df["Close"]

            first_price = prices.iloc[0]
            change = (prices / first_price - 1).dropna()

            returns = change.values.flatten().tolist()

            logger.debug(f"Retrieved {len(returns)} daily returns for {ticker}")
            return returns

        except DataFetchError:
            raise
        except Exception as e:
            logger.error(f"Error fetching index returns for {ticker}: {e}")
            raise DataFetchError(f"Could not fetch returns for {ticker}: {str(e)}") from e

    def get_portfolio_summary(self) -> Dict:
        """
        Get a summary of current portfolio status.

        Returns:
            Dictionary with portfolio summary including current holdings,
            total value, and cash balance

        Example:
            >>> summary = portfolio.get_portfolio_summary()
            >>> print(f"Total value: {summary['total_value']:,.2f}")
        """
        logger.debug("Generating portfolio summary")

        current_date = date.today()
        holdings = get_portfolio(current_date, self.user_id)
        cash = get_cash_balance(current_date, self.user_id) or 0

        total_value = cash

        holdings_details = []
        for ticker, shares in holdings.items():
            try:
                price = get_price(ticker, current_date, self.user_id)
                if price is not None:
                    position_value = shares * price
                    total_value += position_value
                    holdings_details.append(
                        {
                            "ticker": ticker,
                            "shares": shares,
                            "price": price,
                            "value": position_value,
                        }
                    )
            except Exception as e:
                logger.warning(f"Could not get price for {ticker}: {e}")

        return {
            "date": current_date,
            "currency": self.currency,
            "holdings": holdings_details,
            "cash": cash,
            "total_value": total_value,
        }

    def __repr__(self) -> str:
        """Return string representation of portfolio."""
        return (
            f"FinTrack(initial_cash={self.initial_cash}, "
            f"currency={self.currency}, csv_file={self.csv_file})"
        )
