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
            # Add extra days to ensure we get end_date data if available
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date + timedelta(days=3),  # Changed from 1 to 3 days
                progress=False,
            )

            if df.empty:
                raise DataFetchError(f"No data available for {ticker}")

            if isinstance(df.columns, pd.MultiIndex):
                if 'Close' in df.columns.get_level_values(0):
                    close_prices = df.xs('Close', level=0, axis=1)
                    if isinstance(close_prices, pd.DataFrame):
                        close_prices = close_prices.iloc[:, 0]
                elif 'Close' in df.columns.get_level_values(1):
                    close_prices = df.xs('Close', level=1, axis=1)
                    if isinstance(close_prices, pd.DataFrame):
                        close_prices = close_prices.iloc[:, 0]
                else:
                    close_prices = df.iloc[:, 0]
            else:
                if 'Close' in df.columns:
                    close_prices = df['Close']
                else:
                    close_prices = df.iloc[:, 0]

            # NEW: Determine actual available end date
            actual_end_date = close_prices.index.max().date()
            
            # NEW: Use the earlier of requested end_date or actual available data
            effective_end_date = min(end_date, actual_end_date)
            
            # NEW: Log warning if data not available for full range
            if effective_end_date < end_date:
                logger.warning(
                    f"{ticker}: Requested data until {end_date}, but only available until {effective_end_date}. "
                    f"This is normal if markets haven't closed yet or data hasn't been published."
                )
            
            # CHANGED: Use effective_end_date instead of end_date
            date_range = pd.date_range(start=start_date, end=effective_end_date, freq="D")
            
            close_prices = close_prices.reindex(date_range)

            close_prices = close_prices.ffill()
            
            close_prices = close_prices.bfill()

            if close_prices.isna().all():
                raise DataFetchError(f"No valid price data for {ticker}")

            first_price = close_prices.iloc[0]
            if pd.isna(first_price) or first_price == 0:
                raise DataFetchError(f"Invalid starting price for {ticker}")

            change = (close_prices / first_price - 1)

            returns = change.values.flatten().tolist()

            # CHANGED: Updated log message to include effective_end_date
            logger.info(f"Retrieved {len(returns)} daily returns for {ticker} (from {start_date} to {effective_end_date})")
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

    def get_stock_returns(
        self, from_date: date, to_date: date
    ) -> Dict[str, float]:
        """
        Calculate returns for each stock held during the period.

        Accounts for position changes (buys/sells) during the period using
        a Modified Dietz-style calculation.

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Dictionary mapping ticker symbols to returns (as decimals, e.g., 0.062 = 6.2%)

        Example:
            >>> returns = portfolio.get_stock_returns(
            ...     date(2023, 1, 1),
            ...     date(2023, 12, 31)
            ... )
            >>> for ticker, ret in returns.items():
            ...     print(f"{ticker}: {ret:.2%}")
        """
        logger.info(f"Calculating stock returns from {from_date} to {to_date}")

        try:
            df = pd.read_csv(self.csv_file, sep=";")
            df["Date"] = pd.to_datetime(df["Date"]).dt.date
        except Exception as e:
            logger.error(f"Error reading transactions: {e}")
            raise FinTrackError(f"Could not read transactions: {str(e)}") from e

        all_tickers = set()
        
        start_portfolio = get_portfolio(from_date, self.user_id)
        all_tickers.update(start_portfolio.keys())
        
        period_transactions = df[(df["Date"] >= from_date) & (df["Date"] <= to_date)]
        all_tickers.update(period_transactions["Ticker"].unique())

        returns = {}

        for ticker in all_tickers:
            try:
                start_shares = start_portfolio.get(ticker, 0)
                start_price = get_price(ticker, from_date, self.user_id)
                start_value = start_shares * start_price if start_price else 0

                end_portfolio = get_portfolio(to_date, self.user_id)
                end_shares = end_portfolio.get(ticker, 0)
                end_price = get_price(ticker, to_date, self.user_id)
                end_value = end_shares * end_price if end_price else 0

                ticker_transactions = period_transactions[
                    period_transactions["Ticker"] == ticker
                ]
                
                total_bought = 0
                total_sold = 0
                
                for _, transaction in ticker_transactions.iterrows():
                    trans_date = transaction["Date"]
                    trans_price = get_price(ticker, trans_date, self.user_id)
                    
                    if trans_price is None:
                        continue
                        
                    amount = transaction["Amount"]
                    cash_flow = amount * trans_price
                    
                    if transaction["Type"] == "Buy":
                        total_bought += cash_flow
                    else:
                        total_sold += cash_flow

                if end_value == 0 and (start_value > 0 or total_bought > 0):
                    total_invested = start_value + total_bought
                    proceeds = total_sold
                    
                    if total_invested > 0:
                        stock_return = (proceeds - total_invested) / total_invested
                        returns[ticker] = stock_return
                        logger.debug(
                            f"{ticker}: Complete exit - Invested=${total_invested:.2f}, "
                            f"Proceeds=${proceeds:.2f}, Return={stock_return:.2%}"
                        )
                
                elif start_value > 0 or total_bought > 0:

                    net_investment = total_bought - total_sold
                    capital_at_risk = start_value + net_investment
                    
                    if capital_at_risk > 0:
                        gain_loss = end_value - start_value - net_investment
                        stock_return = gain_loss / capital_at_risk
                        returns[ticker] = stock_return
                        logger.debug(
                            f"{ticker}: Start=${start_value:.2f}, Bought=${total_bought:.2f}, "
                            f"Sold=${total_sold:.2f}, End=${end_value:.2f}, Return={stock_return:.2%}"
                        )
                    elif end_value > 0 and total_bought > 0:

                        stock_return = (end_value + total_sold - total_bought - start_value) / (start_value + total_bought)
                        returns[ticker] = stock_return
                        logger.debug(f"{ticker}: Playing with house money, Return={stock_return:.2%}")

            except Exception as e:
                logger.warning(f"Could not calculate return for {ticker}: {e}")
                continue

        logger.info(f"Calculated returns for {len(returns)} stocks")
        return returns

    def print_stock_returns(
        self, from_date: date, to_date: date, sort_by: str = "return"
    ) -> None:
        """
        Print a formatted table of stock returns.

        Args:
            from_date: Start date
            to_date: End date
            sort_by: How to sort results - "return" (default), "ticker", or "alpha"

        Example:
            >>> portfolio.print_stock_returns(
            ...     date(2023, 1, 1),
            ...     date(2023, 12, 31)
            ... )
            Stock Returns (2023-01-01 to 2023-12-31)
            ==========================================
            AAPL         12.50%
            MSFT          8.23%
            TSLA         -5.12%
        """
        returns = self.get_stock_returns(from_date, to_date)
        
        if not returns:
            return("No returns data available for the specified period.")
            return

        ticker_names = {}
        for ticker in returns.keys():
            try:
                yf_ticker = yf.Ticker(ticker)
                long_name = yf_ticker.info.get("longName", ticker)
                ticker_names[ticker] = long_name
            except Exception:
                ticker_names[ticker] = ticker
        r_str = ""
        r_str += (f"\nStock Returns ({from_date} to {to_date})\n")
        r_str += ("=" * 50 + "\n")

        if sort_by == "return":
            sorted_items = sorted(returns.items(), key=lambda x: x[1], reverse=True)
        elif sort_by == "alpha" or sort_by == "ticker":
            sorted_items = sorted(returns.items(), key=lambda x: ticker_names[x[0]])
        else:
            sorted_items = returns.items()

        for ticker, ret in sorted_items:
            name = ticker_names[ticker]
            if len(name) > 40:
                name = name[:37] + "..."
            r_str += (f"{name:<40} {ret:>7.2%}\n")
        
        r_str += ("=" * 50 + "\n")
        
        avg_return = sum(returns.values()) / len(returns) if returns else 0
        r_str += (f"Average Return: {avg_return:>7.2%}")
        return r_str

    def __repr__(self) -> str:
        """Return string representation of portfolio."""
        return (
            f"FinTrack(initial_cash={self.initial_cash}, "
            f"currency={self.currency}, csv_file={self.csv_file})"
        )
