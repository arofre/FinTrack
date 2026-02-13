# Quick Start Guide - FinTrack

Get your portfolio tracking up and running in 5 minutes!

## Installation

```bash
pip install FinTrack
```

## 1. Create Your Transactions File

Create a file called `transactions.csv` with your stock transactions:

```csv
Date;Ticker;Type;Amount;Price
2023-01-15;AAPL;Buy;10;150.00
2023-02-20;MSFT;Buy;5;250.00
2023-03-10;AAPL;Sell;5;165.00
2023-04-05;TSLA;Buy;2;800.00
```

**Required columns:**
- `Date`: Transaction date (YYYY-MM-DD)
- `Ticker`: Stock ticker symbol (e.g., AAPL, MSFT)
- `Type`: Either "Buy" or "Sell"
- `Amount`: Number of shares (integer)
- `Price`: Price per share on transaction date (number)

## 2. Initialize Your Portfolio

Create a Python script (e.g., `my_portfolio.py`):

```python
from portfolio_tracker import Portfolio_tracker
import datetime

# Initialize with your starting cash and base currency
portfolio = Portfolio_tracker(
    initial_cash=150000,      # Your starting cash amount
    currency="SEK",            # Your portfolio's base currency (USD, EUR, SEK, etc.)
    csv_file="transactions.csv"
)

# Update portfolio with latest data
portfolio.update_portfolio()

print("Portfolio initialized successfully!")
```

Run it:
```bash
python my_portfolio.py
```

## 3. Query Your Portfolio

### Get Current Holdings

```python
from portfolio_tracker import Portfolio_tracker
import datetime

portfolio = Portfolio_tracker(
    initial_cash=150000,
    currency="SEK",
    csv_file="transactions.csv"
)

# Get current holdings with company names
current = portfolio.get_current_holdings()
print(f"Current holdings: {current}")

# Example output: ['Apple Inc.', 'Microsoft Corporation', 'Tesla, Inc.']
```

### Get Portfolio Value Over Time

```python
from datetime import date

# Get portfolio value for each day in a date range
values = portfolio.get_portfolio_value(
    from_date=date(2023, 1, 1),
    to_date=date(2023, 12, 31)
)

# Example output:
# {
#   date(2023, 1, 15): 151500.00,
#   date(2023, 2, 20): 152800.00,
#   ...
# }

for date_key, value in sorted(values.items()):
    print(f"{date_key}: {value:,.2f}")
```

### Get Cash Balance

```python
from datetime import date

# Check cash balance at a specific date
cash = portfolio.get_portfolio_cash(date(2023, 6, 15))
print(f"Cash balance on 2023-06-15: {cash:,.2f}")
```

### Compare Against Index

```python
from datetime import date

# Get S&P 500 returns for comparison
index_returns = portfolio.get_index_returns(
    ticker="^GSPC",  # S&P 500
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31)
)

print(f"S&P 500 returns: {index_returns}")
```

## 4. View All Holdings (Past and Present)

```python
# Get all stocks ever held in the portfolio
all_holdings = portfolio.get_past_holdings()
print(f"All past holdings: {all_holdings}")
```

## 5. Update Portfolio (Daily)

The portfolio is automatically updated when you initialize it. For subsequent runs, call update:

```python
portfolio.update_portfolio()  # Fetches latest prices, processes transactions, tracks dividends
```

## Complete Example Script

```python
from portfolio_tracker import Portfolio_tracker
from datetime import date
import pandas as pd

# Initialize
portfolio = Portfolio_tracker(
    initial_cash=150000,
    currency="SEK",
    csv_file="transactions.csv"
)

# Update with latest data
portfolio.update_portfolio()

# Get portfolio metrics
print("Current Holdings")
holdings = portfolio.get_current_holdings()
for holding in holdings:
    print(f"  - {holding}")

print("\nPortfolio Value")
values = portfolio.get_portfolio_value(
    from_date=date(2023, 1, 1),
    to_date=date(2023, 12, 31)
)

# Print first and last value
first_date = min(values.keys())
last_date = max(values.keys())
print(f"Start ({first_date}): {values[first_date]:,.2f}")
print(f"End ({last_date}): {values[last_date]:,.2f}")

print("\nCash Balance")
cash = portfolio.get_portfolio_cash(date(2023, 12, 31))
print(f"Final cash balance: {cash:,.2f}")

print("\nBenchmark Comparison")
index = portfolio.get_index_returns(
    "^GSPC",
    date(2023, 1, 1),
    date(2023, 12, 31)
)
print(f"S&P 500 first day return: {index[0]:.2%}")
print(f"S&P 500 last day return: {index[-1]:.2%}")
```

## Supported Currencies

Use any currency pair available on Yahoo Finance:

```python
# Examples
portfolio = Portfolio_tracker(initial_cash=100000, currency="USD")  # US Dollar
portfolio = Portfolio_tracker(initial_cash=100000, currency="EUR")  # Euro
portfolio = Portfolio_tracker(initial_cash=100000, currency="GBP")  # British Pound
portfolio = Portfolio_tracker(initial_cash=100000, currency="JPY")  # Japanese Yen
portfolio = Portfolio_tracker(initial_cash=100000, currency="SEK")  # Swedish Krona
```

## Multi-Currency Portfolios

The package automatically converts stock prices to your portfolio's base currency:

```python
# Portfolio in EUR, but holding USD stocks
portfolio = Portfolio_tracker(
    initial_cash=100000,
    currency="EUR",
    csv_file="transactions.csv"  # Contains AAPL, MSFT, etc. (USD stocks)
)
# Prices are automatically converted from USD to EUR!
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'portfolio_tracker'"
```bash
pip install FinTrack
```

### "FileNotFoundError: transactions.csv"
Make sure `transactions.csv` exists in your current directory.

### "ValueError: No exchange rate data"
Check your internet connection. The package needs to fetch currency data.

### "No price data for ticker X"
- Verify the ticker symbol is correct (e.g., AAPL, not apple)
- The stock may not trade on the specified date

### Portfolio values seem wrong
- Check that your `transactions.csv` dates are in YYYY-MM-DD format
- Verify Buy/Sell amounts match your records
- Run `portfolio.update_portfolio()` to refresh
- If everything seems to be in order and the difference is small, it could simply be that Yahoo Finance is doing something weird

## Tips & Best Practices

1. **Keep your CSV organized**: One transaction per row, consistent date format
2. **Use correct ticker symbols**: Look them up on Yahoo Finance
3. **Update regularly**: Run `portfolio.update_portfolio()` daily for current data
4. **Backup your data**: Keep your `transactions.csv` safe
5. **Multi-currency**: Works seamlessly with mixed-currency portfolios
6. **Dividends are automatic**: The package fetches and accounts for them automatically

## Next Steps

- Check out the full [README.md](README.md) for advanced features
- Explore [examples](examples/) directory for more use cases
- Read the [CHANGELOG.md](CHANGELOG.md) for latest updates