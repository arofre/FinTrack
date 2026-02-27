"""Tools for parsing transactions and managing portfolio database."""
import sqlite3
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
import os

import pandas as pd
import yfinance as yf

from .config import Config
from .errors import DatabaseError, DataFetchError, PriceError, ValidationError
from .logger import get_logger
from .validation import TransactionValidator
from .yf_tools import (
    get_currency_from_ticker,
    get_exchange_rate,
    get_dividends,
)

logger = get_logger(__name__)


def build_holding_table(csv_file: str, user_id: Optional[str] = None) -> None:
    """
    Parse transactions CSV and create portfolio holdings table.

    Creates a SQLite table tracking the number of shares held for each
    ticker on each transaction date. Short positions are represented as
    negative share counts.

    Transaction type effects on holdings:
        - Buy:   +shares (long position)
        - Sell:  -shares (reduce long position)
        - Short: -shares (open short position, results in negative count)
        - Cover: +shares (close short position)

    Args:
        csv_file: Path to transactions CSV file
        user_id: Optional user identifier

    Raises:
        FileNotFoundError: If CSV file does not exist
        ValidationError: If CSV data is invalid
        DatabaseError: If database operations fail

    Example:
        >>> build_holding_table('transactions.csv')
    """
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Transaction file not found: {csv_file}")

    logger.info(f"Building holding table from {csv_file}")

    try:
        df = pd.read_csv(csv_file, sep=";")
        df["Date"] = pd.to_datetime(df["Date"])

        is_valid, errors = TransactionValidator.validate_dataframe(df)
        if not is_valid:
            raise ValidationError(f"Invalid transaction data:\n" + "\n".join(errors))

        all_dates = sorted(df["Date"].unique())
        all_tickers = sorted(df["Ticker"].unique())

        portfolio_data = []

        for date_val in all_dates:
            row = {"Date": date_val}

            for ticker in all_tickers:
                transactions = df[(df["Ticker"] == ticker) & (df["Date"] <= date_val)]

                if len(transactions) > 0:
                    # Buy and Cover both increase share count
                    # Sell and Short both decrease share count
                    inflows = transactions[
                        transactions["Type"].isin(["Buy", "Cover"])
                    ]["Amount"].sum()
                    outflows = transactions[
                        transactions["Type"].isin(["Sell", "Short"])
                    ]["Amount"].sum()
                    holdings = inflows - outflows

                    if holdings != 0:
                        row[ticker] = holdings
                    else:
                        row[ticker] = None
                else:
                    row[ticker] = None

            portfolio_data.append(row)

        portfolio_df = pd.DataFrame(portfolio_data)
        portfolio_df_filled = portfolio_df.fillna(0)

        db_path = Config.get_db_path(user_id)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS portfolio")
            portfolio_df_filled.to_sql("portfolio", conn, index=False, if_exists="replace")
            conn.commit()

        logger.info(f"Holdings table built successfully with {len(all_tickers)} tickers")

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error building holdings table: {e}")
        raise DatabaseError(f"Failed to build holdings table: {str(e)}") from e


def get_portfolio(target_date: date, user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Get portfolio holdings on a specific date.

    Positive values represent long positions; negative values represent
    open short positions.

    Args:
        target_date: Date to query
        user_id: Optional user identifier

    Returns:
        Dictionary mapping ticker symbols to share counts (negative = short)

    Raises:
        DatabaseError: If database query fails

    Example:
        >>> portfolio = get_portfolio(date(2023, 6, 15))
        >>> portfolio
        {'AAPL': 10, 'MSFT': 5, 'TSLA': -3}  # TSLA is a short position
    """
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    target_date_str = str(target_date)

    try:
        db_path = Config.get_db_path(user_id)
        with sqlite3.connect(db_path) as conn:
            query = """
            SELECT * FROM portfolio
            WHERE DATE(Date) <= ?
            ORDER BY Date DESC
            LIMIT 1
            """

            result = pd.read_sql_query(query, conn, params=(target_date_str,))

            if len(result) == 0:
                return {}

            row = result.iloc[0]

            # Include both long (positive) and short (negative) positions
            holdings = {
                ticker: int(shares)
                for ticker, shares in row.items()
                if ticker != "Date" and shares != 0
            }

            # Sort: longs descending by size first, then shorts ascending
            holdings = dict(
                sorted(holdings.items(), key=lambda x: x[1], reverse=True)
            )

            return holdings

    except Exception as e:
        logger.error(f"Error retrieving portfolio for {target_date}: {e}")
        raise DatabaseError(f"Failed to retrieve portfolio: {str(e)}") from e


def get_cash_balance(
    target_date: date, user_id: Optional[str] = None
) -> Optional[float]:
    """
    Get cash balance on a specific date.

    Returns the most recent cash balance on or before the target date.
    Note: Short sale proceeds are added to cash when the short is opened
    (simplified model).

    Args:
        target_date: Date to query
        user_id: Optional user identifier

    Returns:
        Cash balance in base currency, or None if not found

    Example:
        >>> cash = get_cash_balance(date(2023, 6, 15))
        >>> cash
        145250.75
    """
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    target_date_str = str(target_date)

    try:
        db_path = Config.get_db_path(user_id)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT Cash_Balance FROM cash
                WHERE Date <= ?
                ORDER BY Date DESC
                LIMIT 1
                """,
                (target_date_str,),
            )

            result = cursor.fetchone()

            if result:
                return result[0]
            else:
                return None

    except Exception as e:
        logger.error(f"Error retrieving cash balance: {e}")
        raise DatabaseError(f"Failed to retrieve cash balance: {str(e)}") from e


def get_price(ticker: str, target_date: date, user_id: Optional[str] = None) -> Optional[float]:
    """
    Get stock price for a ticker on a specific date.

    Returns the most recent price on or before the target date.

    Args:
        ticker: Stock ticker symbol
        target_date: Date to query
        user_id: Optional user identifier

    Returns:
        Price in base currency, or None if not available

    Example:
        >>> price = get_price('AAPL', date(2023, 6, 15))
        >>> price
        150.25
    """
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    target_date_str = str(target_date)

    try:
        db_path = Config.get_db_path(user_id)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT Price_SEK FROM prices
                WHERE Ticker = ? AND Date <= ?
                ORDER BY Date DESC
                LIMIT 1
                """,
                (ticker, target_date_str),
            )

            result = cursor.fetchone()

            if result:
                return result[0]
            else:
                return None

    except Exception as e:
        logger.error(f"Error retrieving price for {ticker} on {target_date}: {e}")
        raise PriceError(f"Failed to retrieve price for {ticker}: {str(e)}") from e


def build_cash_table(
    csv_file: str = "transactions.csv",
    initial_cash: float = 150000.0,
    portfolio_currency: str = "SEK",
    user_id: Optional[str] = None,
) -> None:
    """
    Build or update cash table tracking cash balance changes.

    Processes transactions and dividend payments to maintain accurate
    cash balance over time.

    Cash flow rules:
        - Buy:   cash decreases (paying for shares)
        - Sell:  cash increases (receiving proceeds)
        - Short: cash increases (receiving short-sale proceeds)
        - Cover: cash decreases (paying to buy back shares)

    Dividends are only paid on long (positive) positions.

    Args:
        csv_file: Path to transactions CSV
        initial_cash: Starting cash amount
        portfolio_currency: Base currency code
        user_id: Optional user identifier

    Raises:
        DatabaseError: If database operations fail

    Example:
        >>> build_cash_table('transactions.csv', 150000, 'USD')
    """
    logger.info(f"Building/updating cash table")

    try:
        df = pd.read_csv(csv_file, sep=";")
        df["Date"] = pd.to_datetime(df["Date"]).dt.date

        db_path = Config.get_db_path(user_id)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cash'"
            )
            exists = cursor.fetchone() is not None

            if not exists:
                cursor.execute(
                    """
                    CREATE TABLE cash (
                        Date TEXT PRIMARY KEY,
                        Cash_Balance REAL
                    )
                    """
                )

                start_date = df["Date"].min() - timedelta(days=1)
                cursor.execute(
                    "INSERT INTO cash (Date, Cash_Balance) VALUES (?, ?)",
                    (str(start_date), initial_cash),
                )
                conn.commit()

                previous_balance = initial_cash
                last_processed_date = start_date
                is_initial_build = True
                logger.info(
                    f"Building cash table starting {start_date} with {initial_cash:.2f} {portfolio_currency}"
                )
            else:
                cursor.execute(
                    "SELECT Date, Cash_Balance FROM cash ORDER BY Date DESC LIMIT 1"
                )
                result = cursor.fetchone()
                if result:
                    last_processed_date = pd.to_datetime(result[0]).date()
                    previous_balance = result[1]
                    is_initial_build = False
                    logger.info(
                        f"Updating cash table from {last_processed_date} (balance: {previous_balance:.2f} {portfolio_currency})"
                    )
                else:
                    start_date = df["Date"].min()
                    cursor.execute(
                        "INSERT INTO cash (Date, Cash_Balance) VALUES (?, ?)",
                        (str(start_date), initial_cash),
                    )
                    conn.commit()
                    previous_balance = initial_cash
                    last_processed_date = start_date
                    is_initial_build = True

            end_date = datetime.today().date()

            new_transactions = df[df["Date"] > last_processed_date].sort_values("Date")

            portfolio_df = pd.read_sql_query("SELECT * FROM portfolio", conn)
            portfolio_df["Date"] = pd.to_datetime(portfolio_df["Date"]).dt.date
            tickers = [col for col in portfolio_df.columns if col != "Date"]

            events = []

            for _, transaction in new_transactions.iterrows():
                events.append({"date": transaction["Date"], "type": "transaction", "data": transaction})

            logger.debug("Checking for dividends...")
            for ticker in tickers:
                # Only pay dividends on long (positive) positions
                holdings_after = portfolio_df[
                    (portfolio_df["Date"] > last_processed_date) & (portfolio_df[ticker] > 0)
                ]

                if not holdings_after.empty:
                    try:
                        dividends = get_dividends(
                            last_processed_date + timedelta(days=1), end_date, ticker
                        )

                        if not dividends.empty:
                            for div_date, div_amount in dividends.items():
                                div_date = div_date.date()

                                holdings = get_portfolio(div_date, user_id)
                                # Only credit dividend if holding a long position
                                if ticker in holdings and holdings[ticker] > 0:
                                    events.append(
                                        {
                                            "date": div_date,
                                            "type": "dividend",
                                            "data": {
                                                "ticker": ticker,
                                                "amount": div_amount,
                                                "shares": holdings[ticker],
                                            },
                                        }
                                    )
                    except Exception as e:
                        logger.warning(f"Could not fetch dividends for {ticker}: {e}")

            events.sort(key=lambda x: x["date"])

            if not events:
                logger.debug("No new events to process.")
                return

            current_balance = previous_balance

            for event in events:
                event_date = event["date"]

                if event["type"] == "transaction":
                    transaction = event["data"]
                    ticker = transaction["Ticker"]
                    trans_type = transaction["Type"]
                    amount = transaction["Amount"]

                    try:
                        price = get_price(ticker, event_date, user_id)

                        if price is None:
                            logger.warning(
                                f"No price found for {ticker} on {event_date}, skipping transaction"
                            )
                            continue

                        transaction_value = amount * price

                        if trans_type == "Buy":
                            current_balance -= transaction_value
                            logger.debug(
                                f"  {event_date} - Buy: {amount} shares of {ticker} at {price:.2f} {portfolio_currency} = -{transaction_value:.2f} {portfolio_currency}"
                            )
                        elif trans_type == "Sell":
                            current_balance += transaction_value
                            logger.debug(
                                f"  {event_date} - Sell: {amount} shares of {ticker} at {price:.2f} {portfolio_currency} = +{transaction_value:.2f} {portfolio_currency}"
                            )
                        elif trans_type == "Short":
                            # Receive short-sale proceeds
                            current_balance += transaction_value
                            logger.debug(
                                f"  {event_date} - Short: {amount} shares of {ticker} at {price:.2f} {portfolio_currency} = +{transaction_value:.2f} {portfolio_currency} (short proceeds)"
                            )
                        elif trans_type == "Cover":
                            # Pay to buy back shorted shares
                            current_balance -= transaction_value
                            logger.debug(
                                f"  {event_date} - Cover: {amount} shares of {ticker} at {price:.2f} {portfolio_currency} = -{transaction_value:.2f} {portfolio_currency} (cover cost)"
                            )

                        cursor.execute(
                            "INSERT OR REPLACE INTO cash (Date, Cash_Balance) VALUES (?, ?)",
                            (str(event_date), current_balance),
                        )

                    except Exception as e:
                        logger.error(f"Error processing transaction for {ticker}: {e}")
                        continue

                elif event["type"] == "dividend":
                    data = event["data"]
                    ticker = data["ticker"]
                    div_amount = data["amount"]
                    shares_owned = data["shares"]

                    try:
                        total_dividend = div_amount * shares_owned

                        currency = get_currency_from_ticker(ticker)
                        if currency != portfolio_currency:
                            exchange_rate = get_exchange_rate(
                                event_date, event_date, currency, portfolio_currency
                            )
                            if not exchange_rate.empty:
                                total_dividend *= exchange_rate.iloc[0]

                        current_balance += total_dividend
                        logger.debug(
                            f"  {event_date} - Dividend: {ticker} +{total_dividend:.2f} {portfolio_currency} ({shares_owned} shares @ {div_amount:.4f})"
                        )

                        cursor.execute(
                            "INSERT OR REPLACE INTO cash (Date, Cash_Balance) VALUES (?, ?)",
                            (str(event_date), current_balance),
                        )
                    except Exception as e:
                        logger.warning(f"Error processing dividend for {ticker}: {e}")

            conn.commit()

        logger.info(
            f"Cash table {'built' if is_initial_build else 'updated'} successfully!"
        )
        logger.info(f"Processed {len(events)} events. Final balance: {current_balance:.2f} {portfolio_currency}")

    except Exception as e:
        logger.error(f"Error in build_cash_table: {e}")
        raise DatabaseError(f"Failed to build cash table: {str(e)}") from e


def _get_specified_prices(csv_file: str) -> Dict[str, Dict[date, float]]:
    """
    Extract specified transaction prices from CSV.

    Args:
        csv_file: Path to transactions CSV

    Returns:
        Dictionary mapping ticker to dict of dates to prices
    """
    df = pd.read_csv(csv_file, sep=";")

    if "Price" not in df.columns:
        return {}

    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    df_with_prices = df[df["Price"].notna() & (df["Price"] != "") & (df["Price"] != 0)]

    specified_prices = {}

    for ticker in df_with_prices["Ticker"].unique():
        ticker_transactions = df_with_prices[df_with_prices["Ticker"] == ticker]
        specified_prices[ticker] = {}

        for date_val in ticker_transactions["Date"].unique():
            date_transactions = ticker_transactions[ticker_transactions["Date"] == date_val]

            total_shares = date_transactions["Amount"].sum()
            weighted_price = (date_transactions["Amount"] * date_transactions["Price"]).sum() / total_shares

            specified_prices[ticker][date_val] = weighted_price

    return specified_prices


def _fill_prices_forward(
    ticker: str, price_sek: float, start_date: date, end_date: date, cursor: sqlite3.Cursor
) -> None:
    """Fill specified price forward until yfinance data is found."""
    current_date = start_date

    while current_date <= end_date:
        cursor.execute(
            "SELECT 1 FROM prices WHERE Ticker = ? AND Date = ? LIMIT 1",
            (ticker, str(current_date)),
        )

        if cursor.fetchone():
            break

        cursor.execute(
            "SELECT Price_SEK FROM prices WHERE Ticker = ? AND Date = ?",
            (ticker, str(current_date)),
        )

        result = cursor.fetchone()
        if not result:
            cursor.execute(
                "INSERT INTO prices (Date, Ticker, Price_SEK) VALUES (?, ?, ?)",
                (str(current_date), ticker, price_sek),
            )

        current_date += timedelta(days=1)


def generate_price_table(
    portfolio_currency: str = "SEK", csv_file: str = "transactions.csv", user_id: Optional[str] = None
) -> None:
    """
    Generate price table with daily stock prices.

    Fetches prices from Yahoo Finance and converts to portfolio currency.
    Prices are fetched for both long and short positions, since mark-to-market
    valuation requires current prices for all open positions.

    Args:
        portfolio_currency: Base currency code
        csv_file: Path to transactions CSV
        user_id: Optional user identifier

    Raises:
        DatabaseError: If database operations fail

    Example:
        >>> generate_price_table('USD', 'transactions.csv')
    """
    logger.info(f"Generating price table in {portfolio_currency}")

    try:
        db_path = Config.get_db_path(user_id)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
            )
            exists = cursor.fetchone() is not None

            if not exists:
                cursor.execute(
                    """
                    CREATE TABLE prices (
                        Date TEXT,
                        Ticker TEXT,
                        Price_SEK REAL,
                        PRIMARY KEY (Date, Ticker)
                    )
                    """
                )
                cursor.execute("SELECT MIN(Date) FROM portfolio")
                start_date = pd.to_datetime(cursor.fetchone()[0]).date()
            else:
                cursor.execute("SELECT MAX(Date) FROM prices")
                last_date = cursor.fetchone()[0]
                if last_date:
                    start_date = pd.to_datetime(last_date).date() + timedelta(days=1)
                else:
                    cursor.execute("SELECT MIN(Date) FROM portfolio")
                    start_date = pd.to_datetime(cursor.fetchone()[0]).date()

            end_date = datetime.today().date()

            if start_date > end_date:
                logger.debug("Prices table is up to date.")
                return

            logger.info(f"Updating prices from {start_date} to {end_date}...")

            specified_prices = _get_specified_prices(csv_file)
            logger.debug(f"Found specified prices for: {list(specified_prices.keys())}")

            portfolio_df = pd.read_sql_query("SELECT * FROM portfolio", conn)
            portfolio_df["Date"] = pd.to_datetime(portfolio_df["Date"]).dt.date
            portfolio_df = portfolio_df.sort_values("Date")

            tickers = [col for col in portfolio_df.columns if col != "Date"]

            for ticker in tickers:
                logger.debug(f"Processing {ticker}...")

                if ticker in specified_prices:
                    ticker_spec_prices = specified_prices[ticker]
                    logger.debug(f"  Found {len(ticker_spec_prices)} specified prices for {ticker}")

                    try:
                        currency = get_currency_from_ticker(ticker)

                        for spec_date, spec_price_original in ticker_spec_prices.items():
                            if currency != portfolio_currency:
                                logger.debug(
                                    f"    Converting {spec_date} price from {currency} to {portfolio_currency}..."
                                )
                                exchange_rates = get_exchange_rate(
                                    spec_date, spec_date, currency, portfolio_currency
                                )
                                if not exchange_rates.empty:
                                    spec_price_sek = spec_price_original * exchange_rates.iloc[0]
                                else:
                                    logger.warning(
                                        f"    No exchange rate found for {currency} on {spec_date}"
                                    )
                                    spec_price_sek = spec_price_original
                            else:
                                spec_price_sek = spec_price_original

                            cursor.execute(
                                "INSERT OR REPLACE INTO prices (Date, Ticker, Price_SEK) VALUES (?, ?, ?)",
                                (str(spec_date), ticker, float(spec_price_sek)),
                            )
                            logger.debug(
                                f"    Inserted {ticker} price for {spec_date}: {spec_price_sek:.2f} {portfolio_currency}"
                            )

                            fill_end = spec_date + timedelta(days=1)
                            _fill_prices_forward(ticker, float(spec_price_sek), spec_date, fill_end, cursor)

                    except Exception as e:
                        logger.error(f"  Error processing specified prices for {ticker}: {e}")

                ownership_periods = []

                for i, row in portfolio_df.iterrows():
                    date_val = row["Date"]
                    holdings = row[ticker]

                    if i < len(portfolio_df) - 1:
                        period_end = portfolio_df.iloc[i + 1]["Date"] - timedelta(days=1)
                    else:
                        period_end = end_date

                    # Fetch prices for both long (positive) and short (negative) positions
                    if holdings != 0:
                        period_start = max(date_val, start_date)
                        period_end = min(period_end + timedelta(days=1), end_date)

                        if period_start <= period_end:
                            ownership_periods.append((period_start, period_end))

                if not ownership_periods:
                    continue

                merged_periods = []
                current_start, current_end = ownership_periods[0]

                for i in range(1, len(ownership_periods)):
                    next_start, next_end = ownership_periods[i]
                    if next_start <= current_end + timedelta(days=1):
                        current_end = max(current_end, next_end)
                    else:
                        merged_periods.append((current_start, current_end))
                        current_start, current_end = next_start, next_end

                merged_periods.append((current_start, current_end))

                for period_start, period_end in merged_periods:
                    try:
                        logger.debug(f"  Downloading {ticker} from {period_start} to {period_end}...")

                        currency = get_currency_from_ticker(ticker)

                        prices_df = yf.download(
                            ticker,
                            start=period_start,
                            end=period_end + timedelta(days=1),
                            auto_adjust=False,
                            progress=False,
                        )

                        if prices_df.empty:
                            logger.warning(f"  No data returned for {ticker}")
                            continue

                        if "Close" in prices_df.columns:
                            close_prices = prices_df["Close"]
                        else:
                            close_prices = prices_df

                        if isinstance(close_prices, pd.DataFrame):
                            close_prices = close_prices.iloc[:, 0]

                        if currency != portfolio_currency:
                            logger.debug(f"  Converting from {currency} to {portfolio_currency}...")

                            exchange_rates = get_exchange_rate(period_start, period_end, currency, portfolio_currency)

                            exchange_rates_aligned = exchange_rates.reindex(close_prices.index).ffill()
                            exchange_rates_aligned = exchange_rates_aligned.bfill()

                            prices_sek = close_prices * exchange_rates_aligned

                            nan_count = prices_sek.isna().sum()
                            if nan_count > 0:
                                logger.warning(
                                    f"  {nan_count} NaN values after conversion for {ticker}"
                                )
                        else:
                            prices_sek = close_prices

                        inserted_count = 0
                        for date_val, price in prices_sek.items():
                            if pd.notna(price):
                                cursor.execute(
                                    "SELECT Price_SEK FROM prices WHERE Ticker = ? AND Date = ?",
                                    (ticker, str(date_val.date())),
                                )

                                if not cursor.fetchone():
                                    cursor.execute(
                                        "INSERT OR REPLACE INTO prices (Date, Ticker, Price_SEK) VALUES (?, ?, ?)",
                                        (str(date_val.date()), ticker, float(price)),
                                    )
                                    inserted_count += 1

                        logger.debug(f"  Inserted {inserted_count} price records for {ticker}")

                    except Exception as e:
                        logger.error(
                            f"  Error downloading prices for {ticker} from {period_start} to {period_end}: {e}"
                        )
                        continue

            conn.commit()

        logger.info("Price table update complete!")

    except Exception as e:
        logger.error(f"Error in generate_price_table: {e}")
        raise DatabaseError(f"Failed to generate price table: {str(e)}") from e


def get_current_holdings_longnames(user_id: Optional[str] = None) -> List[str]:
    """
    Get current holdings with long company names.

    Includes both long and short positions. Short positions are prefixed
    with "Short: " to make them identifiable.

    Args:
        user_id: Optional user identifier

    Returns:
        List of company long names (short positions prefixed with "Short: ")

    Example:
        >>> holdings = get_current_holdings_longnames()
        >>> holdings
        ['Apple Inc.', 'Microsoft Corporation', 'Short: Tesla, Inc.']
    """
    current_portfolio = get_portfolio(datetime.today().date(), user_id)
    holdings_with_names = []

    for ticker, shares in current_portfolio.items():
        try:
            yf_ticker = yf.Ticker(ticker)
            long_name = yf_ticker.info.get("longName", ticker)
            if shares < 0:
                long_name = f"Short: {long_name}"
            holdings_with_names.append(long_name)
        except Exception as e:
            logger.warning(f"Could not fetch long name for {ticker}: {e}")
            label = f"Short: {ticker}" if shares < 0 else ticker
            holdings_with_names.append(label)

    return holdings_with_names


def get_past_holdings_longnames(user_id: Optional[str] = None) -> List[str]:
    """
    Get all holdings ever owned with long company names.

    Args:
        user_id: Optional user identifier

    Returns:
        List of company long names

    Example:
        >>> holdings = get_past_holdings_longnames()
    """
    db_path = Config.get_db_path(user_id)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(portfolio)")
        columns = cursor.fetchall()

    all_tickers = [col[1] for col in columns if col[1] != "Date"]

    holdings_with_names = []

    for ticker in all_tickers:
        try:
            yf_ticker = yf.Ticker(ticker)
            long_name = yf_ticker.info.get("longName", ticker)
            holdings_with_names.append(long_name)
        except Exception as e:
            logger.warning(f"Could not fetch long name for {ticker}: {e}")
            holdings_with_names.append(ticker)

    return holdings_with_names
