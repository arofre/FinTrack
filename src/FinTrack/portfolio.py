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
    multiple currencies, automatic dividend handling, and short selling.

    Short positions are represented as negative share counts. When you
    short a stock, the proceeds are added to cash. The daily mark-to-market
    value of a short is: proceeds_received - current_cost_to_cover.

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

        Short positions are prefixed with "Short: " in the returned list.

        Returns:
            List of long company names currently held. Short positions are
            prefixed with "Short: " (e.g., "Short: Tesla, Inc.")

        Example:
            >>> holdings = portfolio.get_current_holdings()
            >>> holdings
            ['Apple Inc.', 'Microsoft Corporation', 'Short: Tesla, Inc.']
        """
        logger.debug("Retrieving current holdings")
        return get_current_holdings_longnames(self.user_id)

    def get_past_holdings(self) -> List[str]:
        """
        Get all holdings ever owned with company names.

        Includes positions that have been completely sold or covered.

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

        Note: Cash includes proceeds from short sales (simplified model).

        Args:
            target_date: Date to check cash balance

        Returns:
            Cash balance in base currency, or None if not found

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

        Portfolio value = (long_shares × price) + (short_shares × price) + cash

        For short positions, shares are negative, so their contribution is
        negative (i.e., the mark-to-market cost to cover). Since short
        proceeds were already added to cash when the position was opened,
        the net effect is:
            cash_including_proceeds + (negative_shares × current_price)
            = proceeds - cost_to_cover
            = unrealized P&L on the short

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
        """
        logger.info(f"Calculating portfolio values from {from_date} to {to_date}")

        date_range = pd.date_range(from_date, to_date)
        range_value = {}

        for date_val in date_range:
            target_date = date_val.date()
            portfolio = get_portfolio(target_date, self.user_id)
            value = 0

            if portfolio:
                for ticker, amount in portfolio.items():
                    # amount is positive for longs, negative for shorts
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
                end=end_date + timedelta(days=3),
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

            actual_end_date = close_prices.index.max().date()
            effective_end_date = min(end_date, actual_end_date)

            if effective_end_date < end_date:
                logger.warning(
                    f"{ticker}: Requested data until {end_date}, but only available until {effective_end_date}. "
                    f"This is normal if markets haven't closed yet or data hasn't been published."
                )

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

        Includes both long and short positions. Short positions show
        negative share counts and their current mark-to-market values.

        Returns:
            Dictionary with portfolio summary including current holdings,
            total value, and cash balance. Short positions have negative
            'shares' and 'value' fields.

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
                    position_value = shares * price  # negative for short positions
                    total_value += position_value
                    holdings_details.append(
                        {
                            "ticker": ticker,
                            "shares": shares,          # negative = short
                            "price": price,
                            "value": position_value,   # negative = short liability
                            "is_short": shares < 0,
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

        Handles long positions, short positions, and mixed activity.

        For long positions: standard return on invested capital.
        For short positions: return is calculated as
            (proceeds_received - cost_to_cover) / proceeds_received.
        For mixed (e.g., long then shorted, or short then covered): uses a
        Modified Dietz-style approach treating Short as a cash inflow and
        Cover as a cash outflow, consistent with long Buy/Sell logic.

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Dictionary mapping ticker symbols to returns (as decimals,
            e.g., 0.062 = 6.2%). Negative returns indicate losses.

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
                # For shorts, start_shares is negative → start_value is negative
                start_value = start_shares * start_price if start_price else 0

                end_portfolio = get_portfolio(to_date, self.user_id)
                end_shares = end_portfolio.get(ticker, 0)
                end_price = get_price(ticker, to_date, self.user_id)
                # For shorts, end_shares is negative → end_value is negative
                end_value = end_shares * end_price if end_price else 0

                ticker_transactions = period_transactions[
                    period_transactions["Ticker"] == ticker
                ]

                # Cash outflows: Buy (acquiring longs) and Cover (closing shorts)
                # Cash inflows: Sell (closing longs) and Short (opening shorts)
                total_outflows = 0   # cash spent
                total_inflows = 0    # cash received

                for _, transaction in ticker_transactions.iterrows():
                    trans_date = transaction["Date"]
                    trans_price = get_price(ticker, trans_date, self.user_id)

                    if trans_price is None:
                        continue

                    amount = transaction["Amount"]
                    cash_flow = amount * trans_price

                    if transaction["Type"] in ("Buy", "Cover"):
                        total_outflows += cash_flow
                    else:  # Sell, Short
                        total_inflows += cash_flow

                # Net capital deployed: positive = net cash spent, negative = net cash received
                net_investment = total_outflows - total_inflows

                # Total capital at risk = opening position value + net new capital deployed
                # Works for longs (positive start_value) and shorts (negative start_value,
                # which means we received cash, so capital_at_risk reflects net exposure)
                capital_at_risk = start_value + net_investment

                # Gain/loss = closing value - opening value - net new capital
                gain_loss = end_value - start_value - net_investment

                # Fully closed position
                if end_value == 0 and (start_value != 0 or total_outflows > 0 or total_inflows > 0):
                    total_deployed = abs(start_value) + total_outflows
                    if total_deployed > 0:
                        # For a pure short-then-covered: start_value=0, outflows=cover cost, inflows=proceeds
                        # gain_loss = 0 - 0 - (cover - proceeds) = proceeds - cover
                        stock_return = gain_loss / total_deployed if total_deployed else 0
                        returns[ticker] = stock_return
                        logger.debug(
                            f"{ticker}: Closed - start={start_value:.2f}, "
                            f"outflows={total_outflows:.2f}, inflows={total_inflows:.2f}, "
                            f"Return={stock_return:.2%}"
                        )

                # Open position (long or short)
                elif capital_at_risk != 0:
                    stock_return = gain_loss / abs(capital_at_risk)
                    returns[ticker] = stock_return
                    logger.debug(
                        f"{ticker}: Open - start={start_value:.2f}, end={end_value:.2f}, "
                        f"net_investment={net_investment:.2f}, Return={stock_return:.2%}"
                    )

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

        Short positions are labelled with "(Short)" next to the company name.

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
            TSLA (Short) -5.12%
        """
        returns = self.get_stock_returns(from_date, to_date)

        if not returns:
            return "No returns data available for the specified period."

        end_portfolio = get_portfolio(to_date, self.user_id)

        ticker_names = {}
        for ticker in returns.keys():
            try:
                yf_ticker = yf.Ticker(ticker)
                long_name = yf_ticker.info.get("longName", ticker)
                # Label short positions
                if end_portfolio.get(ticker, 0) < 0:
                    long_name = f"{long_name} (Short)"
                ticker_names[ticker] = long_name
            except Exception:
                ticker_names[ticker] = ticker

        r_str = ""
        r_str += (f"\nStock Returns ({from_date} to {to_date})\n")
        r_str += ("=" * 50 + "\n")

        if sort_by == "return":
            sorted_items = sorted(returns.items(), key=lambda x: x[1], reverse=True)
        elif sort_by in ("alpha", "ticker"):
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
