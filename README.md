# FinTrack

A Python package for tracking a dynamic portfolio of stocks with daily price monitoring, cash management, and dividend handling. This tool helps you maintain a record of your stock holdings, monitor their values over time, and automatically track cash flows from transactions and dividends.

## Features

- **Portfolio Management**: Track multiple stock holdings with buy/sell transactions
- **Dynamic Price Tracking**: Automatically fetch and store historical stock prices using yfinance
- **Multi-Currency Support**: Handle stocks traded in different currencies with automatic conversion
- **Cash Management**: Maintain accurate cash balances accounting for buy/sell transactions and dividend payments
- **Dividend Tracking**: Automatically capture and account for dividend payments
- **Historical Analysis**: Query portfolio composition and value at any point in time
- **Index Comparison**: Compare your portfolio returns against benchmark indices

## Installation

Install the package using pip:

```bash
pip install FinTrack
```

## Quick Start

### 1. Create a Transaction CSV File

First, create a CSV file with your transactions (`transactions.csv`):

```
Date;Ticker;Type;Amount;Price
2023-01-15;AAPL;Buy;10;150.00
2023-02-20;MSFT;Buy;5;250.00
2023-03-10;AAPL;Sell;5;165.00
```

**CSV Columns:**
- `Date`: Transaction date (YYYY-MM-DD format)
- `Ticker`: Stock ticker symbol
- `Type`: Either "Buy" or "Sell"
- `Amount`: Number of shares
- `Price`: Price per share (in the stock's native currency)

### 2. Initialize the Portfolio Tracker

```python
from FinTrack import FinTrack
import datetime

# Initialize with starting cash and currency
portfolio = FinTrack(
    initial_cash=150000,
    currency="SEK",  # Your portfolio's base currency
    csv_file="transactions.csv"
)

# Update portfolio (fetches latest prices and processes new transactions)
portfolio.update_portfolio()
```

### 3. Query Your Portfolio

```python
# Get current holdings
current_holdings = portfolio.get_current_holdings()
print(f"Current holdings: {current_holdings}")

# Get all holdings ever owned
all_holdings = portfolio.get_past_holdings()
print(f"All past holdings: {all_holdings}")

# Get portfolio value for a date range
portfolio_values = portfolio.get_portfolio_value(
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31)
)

# Get cash balance at a specific date
cash_balance = portfolio.get_portfolio_cash(datetime.date(2023, 6, 15))
print(f"Cash balance: {cash_balance}")

# Compare against index returns
index_returns = portfolio.get_index_returns(
    ticker="^GSPC",  # S&P 500
    start_date=datetime.date(2023, 1, 1),
    end_date=datetime.date(2023, 12, 31)
)
```

## How It Works

### Data Storage

The package uses SQLite to store three main tables:

1. **Portfolio Table**: Tracks holdings for each date based on transactions
2. **Cash Table**: Maintains cash balance accounting for transactions and dividends
3. **Prices Table**: Stores historical prices for all stocks in the portfolio

### Price Management

- Prices are automatically fetched from Yahoo Finance using yfinance
- Multi-currency portfolios are supported with automatic conversion to your base currency
- Prices are forward-filled for missing trading days
- You can specify custom prices for specific dates by adding a "Prices" sheet to your CSV

### Cash Flow Tracking

Cash balance is updated for:
- Stock purchases (cash out)
- Stock sales (cash in)
- Dividend payments (cash in)

## Advanced Features

### Custom Price Specifications

You can specify custom prices for certain dates by including them in your transaction CSV. The package will use these instead of fetching from Yahoo Finance when available.

### Portfolio Reset

Reset your portfolio to start fresh:

```python
portfolio.reset_portfolio()
```

## Requirements

- Python >= 3.7
- pandas
- yfinance

## Supported Currencies

The package supports any currency pair available on Yahoo Finance, including:
- Major currencies: USD, EUR, GBP, JPY, CHF, AUD, CAD, SEK, NOK, DKK
- Cryptocurrencies through crypto tickers
- Emerging market currencies

## Limitations

- Prices are fetched from Yahoo Finance; ensure data quality
- Intra-day trading is not supported (daily resolution only)
- Corporate actions (stock splits, mergers) should be manually adjusted in transactions
- Past dividend data depends on Yahoo Finance's historical dividend records

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request on GitHub.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

Always verify your portfolio calculations independently. The author is not responsible for any financial losses resulting from the use of this software.

## Support

For issues, questions, or suggestions, please open an issue on the GitHub repository.
