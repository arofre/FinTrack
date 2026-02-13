import yfinance as yf
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from .yf_tools import get_currency_from_ticker, get_exchange_rate, get_dividends
from datetime import datetime, timedelta

def build_holding_table(csv_file: str) -> None:
    '''
    Given a transaction csv file parses and creates a db for the holdings
    '''
    df = pd.read_csv(csv_file, sep=';')
    df['Date'] = pd.to_datetime(df['Date'])

    all_dates = sorted(df['Date'].unique())
    all_tickers = sorted(df['Ticker'].unique())

    portfolio_data = []

    for date in all_dates:
        row = {'Date': date}
        
        for ticker in all_tickers:
            transactions = df[(df['Ticker'] == ticker) & (df['Date'] <= date)]
            
            if len(transactions) > 0:
                buys = transactions[transactions['Type'] == 'Buy']['Amount'].sum()
                sells = transactions[transactions['Type'] == 'Sell']['Amount'].sum()
                holdings = buys - sells
                
                if holdings > 0:
                    row[ticker] = holdings
                else:
                    row[ticker] = None
            else:
                row[ticker] = None
        
        portfolio_data.append(row)

    portfolio_df = pd.DataFrame(portfolio_data)

    portfolio_df_filled = portfolio_df.fillna(0)


    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS portfolio')

    portfolio_df_filled.to_sql('portfolio', conn, index=False, if_exists='replace')

    conn.commit()
    conn.close()


def get_portfolio(target_date: str) -> dict:
    '''
    Given a target date and portfolio db path returns a dict of what holdings the portfolio has on that day
    '''
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()
    
    target_date_str = str(target_date)
    
    conn = sqlite3.connect('portfolio.db')
    
    query = """
    SELECT * FROM portfolio 
    WHERE DATE(Date) <= ? 
    ORDER BY Date DESC 
    LIMIT 1
    """
    
    result = pd.read_sql_query(query, conn, params=(target_date_str,))
    conn.close()
    
    if len(result) == 0:
        return {}, None
    
    row = result.iloc[0]
    
    holdings = {ticker: int(shares) for ticker, shares in row.items() 
                if ticker != 'Date' and shares > 0}
    
    holdings = dict(sorted(holdings.items(), key=lambda x: x[1], reverse=True))
    
    return holdings

def build_cash_table(csv_file: str = 'transactions.csv', initial_cash: float = 150000.0, PORTFOLIO_CURRENCY='SEK'):
    '''
    Builds or updates the cash table tracking cash balance changes.
    Only creates entries when cash changes (transactions or dividends).
    '''
    
    df = pd.read_csv(csv_file, sep=';')
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cash'")
    exists = cursor.fetchone() is not None
    
    if not exists:
        cursor.execute("""
            CREATE TABLE cash (
                Date TEXT PRIMARY KEY,
                Cash_Balance REAL
            )
        """)
        
        start_date = df['Date'].min() - timedelta(days=1)

        cursor.execute("INSERT INTO cash (Date, Cash_Balance) VALUES (?, ?)", 
                      (str(start_date), initial_cash))
        conn.commit()
        
        previous_balance = initial_cash
        last_processed_date = start_date
        is_initial_build = True
        print(f"Building cash table starting {start_date} with {initial_cash:.2f} SEK")
    else:
        cursor.execute("SELECT Date, Cash_Balance FROM cash ORDER BY Date DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            last_processed_date = pd.to_datetime(result[0]).date()
            previous_balance = result[1]
            is_initial_build = False
            print(f"Updating cash table from {last_processed_date} (balance: {previous_balance:.2f} SEK)")
        else:
            start_date = df['Date'].min()
            cursor.execute("INSERT INTO cash (Date, Cash_Balance) VALUES (?, ?)", 
                          (str(start_date), initial_cash))
            conn.commit()
            previous_balance = initial_cash
            last_processed_date = start_date
            is_initial_build = True
    
    end_date = datetime.today().date()
    
    new_transactions = df[df['Date'] > last_processed_date].sort_values('Date')
    
    portfolio_df = pd.read_sql_query("SELECT * FROM portfolio", conn)
    portfolio_df['Date'] = pd.to_datetime(portfolio_df['Date']).dt.date
    tickers = [col for col in portfolio_df.columns if col != 'Date']
    
    events = []
    
    for _, transaction in new_transactions.iterrows():
        events.append({
            'date': transaction['Date'],
            'type': 'transaction',
            'data': transaction
        })
    
    print("Checking for dividends...")
    for ticker in tickers:
        holdings_after = portfolio_df[
            (portfolio_df['Date'] > last_processed_date) & 
            (portfolio_df[ticker] > 0)
        ]
        
        if not holdings_after.empty:
            try:
                dividends = get_dividends(last_processed_date + timedelta(days=1), end_date, ticker)
                
                if not dividends.empty:
                    for div_date, div_amount in dividends.items():
                        div_date = div_date.date()
                        
                        holdings = get_portfolio(div_date)
                        if ticker in holdings and holdings[ticker] > 0:
                            events.append({
                                'date': div_date,
                                'type': 'dividend',
                                'data': {
                                    'ticker': ticker,
                                    'amount': div_amount,
                                    'shares': holdings[ticker]
                                }
                            })
            except Exception as e:
                pass
    
    events.sort(key=lambda x: x['date'])
    
    if not events:
        print("No new events to process.")
        conn.close()
        return
    
    current_balance = previous_balance
    
    for event in events:
        event_date = event['date']
        
        if event['type'] == 'transaction':
            transaction = event['data']
            ticker = transaction['Ticker']
            trans_type = transaction['Type']
            amount = transaction['Amount']
            
            price = get_price(ticker, event_date)
            
            if price is None:
                print(f"Warning: No price found for {ticker} on {event_date}, skipping transaction")
                continue
            
            transaction_value = amount * price
            
            if trans_type == 'Buy':
                current_balance -= transaction_value
                print(f"  {event_date} - Buy: {amount} shares of {ticker} at {price:.2f} SEK = -{transaction_value:.2f} SEK")
            elif trans_type == 'Sell':
                current_balance += transaction_value
                print(f"  {event_date} - Sell: {amount} shares of {ticker} at {price:.2f} SEK = +{transaction_value:.2f} SEK")
            
            cursor.execute("""
                INSERT OR REPLACE INTO cash (Date, Cash_Balance)
                VALUES (?, ?)
            """, (str(event_date), current_balance))
        
        elif event['type'] == 'dividend':
            data = event['data']
            ticker = data['ticker']
            div_amount = data['amount']
            shares_owned = data['shares']
            
            total_dividend = div_amount * shares_owned
            
            currency = get_currency_from_ticker(ticker)
            if currency != PORTFOLIO_CURRENCY:
                exchange_rate = get_exchange_rate(event_date, event_date, currency, PORTFOLIO_CURRENCY)
                if not exchange_rate.empty:
                    total_dividend *= exchange_rate.iloc[0]
            
            current_balance += total_dividend
            print(f"  {event_date} - Dividend: {ticker} +{total_dividend:.2f} SEK ({shares_owned} shares @ {div_amount:.4f})")
            
            cursor.execute("""
                INSERT OR REPLACE INTO cash (Date, Cash_Balance)
                VALUES (?, ?)
            """, (str(event_date), current_balance))
    
    conn.commit()
    conn.close()
    
    print(f"\nCash table {'built' if is_initial_build else 'updated'} successfully!")
    print(f"Processed {len(events)} events. Final balance: {current_balance:.2f} SEK")


def get_cash_balance(target_date) -> float:
    '''
    Returns the cash balance on a specific date.
    Since the cash table is sparse (only contains entries when balance changes),
    this returns the most recent balance on or before the target date.
    '''
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()
    
    target_date_str = str(target_date)
    
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT Cash_Balance FROM cash 
        WHERE Date <= ?
        ORDER BY Date DESC
        LIMIT 1
    """, (target_date_str,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result[0]
    else:
        return None


def get_price(ticker: str, target_date) -> float:
    """
    Returns the price in SEK for a given ticker on a specific date.
    If no price exists on that date, returns the most recent previous price.
    """

    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    target_date_str = str(target_date)

    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Price_SEK FROM prices
        WHERE Ticker = ? AND Date <= ?
        ORDER BY Date DESC
        LIMIT 1
    """, (ticker, target_date_str))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    else:
        return None


def _get_specified_prices(csv_file: str) -> dict:
    """
    Builds a dict of specified transaction prices by ticker and date.
    Calculates weighted average for multiple transactions same ticker/date.
    
    Returns:
        dict: {ticker: {date: price_in_original_currency}}
    """
    df = pd.read_csv(csv_file, sep=';')
    
    if 'Price' not in df.columns:
        return {}
    
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    
    df_with_prices = df[df['Price'].notna() & (df['Price'] != '') & (df['Price'] != 0)]
    
    specified_prices = {}
    
    for ticker in df_with_prices['Ticker'].unique():
        ticker_transactions = df_with_prices[df_with_prices['Ticker'] == ticker]
        specified_prices[ticker] = {}
        
        for date in ticker_transactions['Date'].unique():
            date_transactions = ticker_transactions[ticker_transactions['Date'] == date]
            
            total_shares = date_transactions['Amount'].sum()
            weighted_price = (date_transactions['Amount'] * date_transactions['Price']).sum() / total_shares
            
            specified_prices[ticker][date] = weighted_price
    
    return specified_prices


def _fill_prices_forward(ticker: str, price_sek: float, start_date, end_date, cursor) -> None:
    """
    Fills specified price forward from start_date until yfinance data is available.
    Stops filling when yfinance data is found.
    """
    current_date = start_date
    
    while current_date <= end_date:
        cursor.execute("""
            SELECT 1 FROM prices 
            WHERE Ticker = ? AND Date = ? 
            LIMIT 1
        """, (ticker, str(current_date)))
        
        if cursor.fetchone():
            break
        
        cursor.execute("""
            SELECT Price_SEK FROM prices 
            WHERE Ticker = ? AND Date = ?
        """, (ticker, str(current_date)))
        
        result = cursor.fetchone()
        if not result:
            cursor.execute("""
                INSERT INTO prices (Date, Ticker, Price_SEK)
                VALUES (?, ?, ?)
            """, (str(current_date), ticker, price_sek))
        
        current_date += timedelta(days=1)


def generate_price_table(PORTFOLIO_CURRENCY='SEK', csv_file='transactions.csv'):
    '''
    Populates the prices table with daily stock prices converted to selected currency.
    Handles specified transaction prices and fills forward until yfinance data.
    Updates incrementally if table exists, otherwise builds from scratch.
    '''
    
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'")
    exists = cursor.fetchone() is not None
    
    if not exists:
        cursor.execute("""
            CREATE TABLE prices (
                Date TEXT,
                Ticker TEXT,
                Price_SEK REAL,
                PRIMARY KEY (Date, Ticker)
            )
        """)
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
        conn.close()
        print("Prices table is up to date.")
        return
    
    print(f"Updating prices from {start_date} to {end_date}...")
    
    specified_prices = _get_specified_prices(csv_file)
    print(f"Found specified prices for: {list(specified_prices.keys())}")
    
    portfolio_df = pd.read_sql_query("SELECT * FROM portfolio", conn)
    portfolio_df['Date'] = pd.to_datetime(portfolio_df['Date']).dt.date
    portfolio_df = portfolio_df.sort_values('Date')
    
    tickers = [col for col in portfolio_df.columns if col != 'Date']
    
    for ticker in tickers:
        print(f"Processing {ticker}...")
        
        if ticker in specified_prices:
            ticker_spec_prices = specified_prices[ticker]
            print(f"  Found {len(ticker_spec_prices)} specified prices for {ticker}")
            
            try:
                currency = get_currency_from_ticker(ticker)
                
                for spec_date, spec_price_original in ticker_spec_prices.items():
                    if currency != PORTFOLIO_CURRENCY:
                        print(f"    Converting {spec_date} price from {currency} to {PORTFOLIO_CURRENCY}...")
                        exchange_rates = get_exchange_rate(spec_date, spec_date, currency, PORTFOLIO_CURRENCY)
                        if not exchange_rates.empty:
                            spec_price_sek = spec_price_original * exchange_rates.iloc[0]
                        else:
                            print(f"    Warning: No exchange rate found for {currency} on {spec_date}, using original price")
                            spec_price_sek = spec_price_original
                    else:
                        spec_price_sek = spec_price_original
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO prices (Date, Ticker, Price_SEK)
                        VALUES (?, ?, ?)
                    """, (str(spec_date), ticker, float(spec_price_sek)))
                    print(f"    Inserted {ticker} price for {spec_date}: {spec_price_sek:.2f} SEK")
                    

                    fill_end = spec_date + timedelta(days=1)
                    _fill_prices_forward(ticker, float(spec_price_sek), spec_date , fill_end, cursor)
            
            except Exception as e:
                print(f"  Error processing specified prices for {ticker}: {e}")
                import traceback
                traceback.print_exc()
        
        ownership_periods = []
        
        for i, row in portfolio_df.iterrows():
            date = row['Date']
            holdings = row[ticker]
            
            if i < len(portfolio_df) - 1:
                period_end = portfolio_df.iloc[i+1]['Date'] - timedelta(days=1)
            else:
                period_end = end_date
            
            if holdings > 0:
                period_start = max(date, start_date)
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
                print(f"  Downloading {ticker} from {period_start} to {period_end}...")
                
                currency = get_currency_from_ticker(ticker)
                
                prices_df = yf.download(ticker, 
                                       start=period_start, 
                                       end=period_end + timedelta(days=1),
                                       auto_adjust=False, 
                                       progress=False)
                
                if prices_df.empty:
                    print(f"  Warning: No data returned for {ticker}")
                    continue
                
                if 'Close' in prices_df.columns:
                    close_prices = prices_df['Close']
                else:
                    close_prices = prices_df
                
                if isinstance(close_prices, pd.DataFrame):
                    close_prices = close_prices.iloc[:, 0]
                
                if currency != PORTFOLIO_CURRENCY:
                    print(f"  Converting from {currency} to {PORTFOLIO_CURRENCY}...")
                    
                    exchange_rates = get_exchange_rate(period_start, period_end, currency, PORTFOLIO_CURRENCY)
                    
                    exchange_rates_aligned = exchange_rates.reindex(close_prices.index, method='ffill')
                    exchange_rates_aligned = exchange_rates_aligned.fillna(method='bfill')
                    
                    prices_sek = close_prices * exchange_rates_aligned
                    
                    nan_count = prices_sek.isna().sum()
                    if nan_count > 0:
                        print(f"  WARNING: {nan_count} NaN values after conversion for {ticker}")
                else:
                    prices_sek = close_prices
                
                inserted_count = 0
                for date, price in prices_sek.items():
                    if pd.notna(price):
                        cursor.execute("""
                            SELECT Price_SEK FROM prices 
                            WHERE Ticker = ? AND Date = ?
                        """, (ticker, str(date.date())))
                        
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT OR REPLACE INTO prices (Date, Ticker, Price_SEK)
                                VALUES (?, ?, ?)
                            """, (str(date.date()), ticker, float(price)))
                            inserted_count += 1
                
                print(f"  Inserted {inserted_count} price records for {ticker}")
                
            except Exception as e:
                print(f"  Error downloading prices for {ticker} from {period_start} to {period_end}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    conn.commit()
    conn.close()
    print("Price table update complete!")


def get_current_holdings_longnames() -> dict:
    '''
    Returns a dictionary of current holdings with their company long names.
    
    Returns:
        list: Long names of all holdings currently
    '''
    current_portfolio = get_portfolio(datetime.today().date())
    holdings_with_names = []
    
    for ticker in current_portfolio.keys():
        try:
            yf_ticker = yf.Ticker(ticker)
            long_name = yf_ticker.info.get('longName', ticker)
            holdings_with_names.append(long_name)
        except Exception as e:
            print(f"Warning: Could not fetch long name for {ticker}: {e}")
            holdings_with_names.append(ticker)
    
    return holdings_with_names


def get_past_holdings_longnames() -> dict:
    '''
    Returns a dictionary of ALL holdings ever owned (including sold positions) with their company long names.
    
    Returns:
        list: Long names of all holdings every recorded
    '''
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = cursor.fetchall()
    conn.close()
    
    all_tickers = [col[1] for col in columns if col[1] != 'Date']
    
    holdings_with_names = []
    
    for ticker in all_tickers:
        try:
            yf_ticker = yf.Ticker(ticker)
            long_name = yf_ticker.info.get('longName', ticker)
            holdings_with_names.append(long_name)
        except Exception as e:
            print(f"Warning: Could not fetch long name for {ticker}: {e}")
            holdings_with_names.append(ticker)
    
    return holdings_with_names