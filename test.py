from portfolio import Portfolio_tracker
import datetime
portfolio = Portfolio_tracker(initial_cash=150000, currency="SEK", csv_file="transactions.csv")

value = portfolio.get_portfolio_value(datetime.date(2025,2,18), datetime.date(2026,2,13))
print(portfolio.get_portfolio_cash(datetime.date(2026,2,12)))