import yfinance as yf
import datetime
import pandas as pd

def get_returns(from_date: datetime.date, to_date: datetime.date, ticker: str) -> pd.DataFrame:
    '''
    Returns the percentage diff between a dates non adjusted close and the previous days non adjusted close
    '''
    prices = yf.download(ticker, 
                start=from_date, 
                end=to_date + datetime.timedelta(days=1),
                auto_adjust=False)
    
    date_range = pd.date_range(start=from_date, end=to_date + datetime.timedelta(days=1), freq='D')
    prices = prices.reindex(date_range)
    prices = prices.ffill()
    returns = prices['Close'].pct_change().fillna(0) + 1
    return returns


def get_dividends(from_date: datetime.date, to_date: datetime.date, ticker: str) -> pd.DataFrame:
    '''
    Gives a dataframe of dividends between two dates
    '''
    yf_ticker = yf.Ticker(ticker)
    dividends = yf_ticker.dividends

    dividends.index = dividends.index.tz_localize(None)

    from_dt = datetime.datetime.combine(from_date, datetime.time.min)
    to_dt = datetime.datetime.combine(to_date, datetime.time.max)
    
    return dividends[(dividends.index >= from_dt) & (dividends.index <= to_dt)]


def get_exchange_rate(from_date: datetime.date, to_date: datetime.date, from_currency: str, to_currency: str) -> pd.Series:
    '''
    Returns a Series of exchange rates between two dates.
    '''
    exchange_ticker = f'{from_currency}{to_currency}=X'
    if from_currency == "GBp":
        exchange_ticker = f"GBP{to_currency}=X"

    rate_df = yf.download(exchange_ticker, 
                          start=from_date, 
                          end=to_date + datetime.timedelta(days=1), 
                          auto_adjust=False,
                          progress=False)
    
    if rate_df.empty:
        raise ValueError(f"No exchange rate data available for {exchange_ticker}")
    
    if 'Close' in rate_df.columns:
        if isinstance(rate_df['Close'], pd.DataFrame):
            rate = rate_df['Close'][exchange_ticker]
        else:
            rate = rate_df['Close']
    else:
        rate = rate_df.iloc[:, 0]
    
    if from_currency == "GBp":
        rate = rate / 100
    
    date_range = pd.date_range(start=from_date, end=to_date, freq='D')
    rate = rate.reindex(date_range, method='ffill')
    
    rate = rate.fillna(method='bfill')
    
    return rate


def get_currency_from_ticker(ticker: str) -> str:
    '''
    Given a string for a yfinance ticker, returns the currency the stock is traded in
    '''
    yf_ticker = yf.Ticker(ticker)
    return yf_ticker.info['currency']