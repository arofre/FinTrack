from .yf_tools import *
from .parsing_tools import *
import datetime 
import pandas as pd 


class FinTrack:
    '''
    initial_cash = integer representing the initial cash for the cash management system
    currency = string of the currency used, EX: USD, EUR etc
    csv_file = string of the name for the transaction csv file
    '''
    def __init__(self, initial_cash: int, currency: str, csv_file: str):
        self.initial_cash = initial_cash
        self.currency = currency
        self.csv_file = csv_file
        build_holding_table(csv_file=self.csv_file)
        generate_price_table(PORTFOLIO_CURRENCY=self.currency)
        build_cash_table(csv_file=self.csv_file, initial_cash=self.initial_cash, PORTFOLIO_CURRENCY=self.currency)


    def update_portfolio(self):
        build_holding_table(csv_file=self.csv_file)
        generate_price_table(PORTFOLIO_CURRENCY=self.currency)
        build_cash_table(csv_file=self.csv_file, initial_cash=self.initial_cash, PORTFOLIO_CURRENCY=self.currency)

    def reset_portfolio(self):
        pass

    def get_portfolio_cash(self, date: datetime.date):
        return get_cash_balance(date)

    def get_index_returns(self, ticker, start_date, end_date):

        df = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1), progress=False)

        df = df.asfreq("D")

        df["Close"] = df["Close"].ffill()

        prices = df["Close"]

        first_price = prices.iloc[0]
        change = (prices / first_price - 1).dropna()

        returns = change.values.flatten().tolist()

        return returns

    def get_current_holdings(self):
        return get_current_holdings_longnames()
    
    def get_past_holdings(self):
        return get_past_holdings_longnames()

    def get_portfolio_value(self, from_date:datetime.date, to_date:datetime.date) -> list:
        date_range = pd.date_range(from_date, to_date)
        range_value = {}
        for date in date_range:
            portfolio = get_portfolio(date)
            value = 0
            if not type(portfolio) == tuple:
                for ticker in portfolio.keys():
                    amount = portfolio[ticker]
                    try:
                        value += amount * get_price(ticker, date.date())
                    except:
                        raise Exception(f"Error with {ticker} on {date}")
            
            value += get_cash_balance(date)

            range_value[date.date()] = value
        
        return range_value