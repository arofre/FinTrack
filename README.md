# FinTrack - Advanced Portfolio Tracker

[![Tests](https://img.shields.io/badge/tests-passing-green)](./tests)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A Python package for tracking and analyzing stock portfolios with multi-currency support, automatic dividend tracking, and short selling.

## Important note

Tests, instructions and docstrings written using Claude, I tried to find any incorrect information but some may have slipped through the crack.

## Features

- **Portfolio Management**: Track multiple stock holdings with buy/sell transactions
- **Short Selling**: Open and close short positions with mark-to-market daily valuation
- **Dynamic Price Tracking**: Automatically fetch and store historical stock prices using yfinance
- **Multi-Currency Support**: Handle stocks traded in different currencies with automatic conversion
- **Cash Management**: Maintain accurate cash balances accounting for all transaction types and dividend payments
- **Dividend Tracking**: Automatically capture and account for dividend payments (long positions only)
- **Historical Analysis**: Query portfolio composition and value at any point in time
- **Stock Returns Analysis**: Calculate individual stock performance including short positions
- **Index Comparison**: Compare your portfolio returns against benchmark indices
- **Comprehensive Logging**: Track all operations with detailed logging
- **Input Validation**: Validate all transaction data before processing

## Installation

Install the package using pip:

```bash
pip install FinTrack
```

For development:
```bash
git clone https://github.com/arofredriksson/FinTrack.git
cd FinTrack
pip install -e ".[dev]"
pytest tests/
```

## Quick Start

### 1. Create a Transaction CSV

Create `transactions.csv`:
```csv
Date;Ticker;Type;Amount;Price
2023-01-15;AAPL;Buy;10;150.00
2023-02-20;MSFT;Buy;5;250.00
2023-03-10;AAPL;Sell;5;165.00
2023-04-05;TSLA;Buy;2;800.00
2023-06-01;TSLA;Short;3;290.00
2023-09-15;TSLA;Cover;3;240.00
```

### 2. Initialize and Query

```python
from FinTrack import FinTrack
from datetime import date

# Create portfolio
portfolio = FinTrack(
    initial_cash=150000,
    currency="USD",
    csv_file="transactions.csv"
)

# Update with latest data
portfolio.update_portfolio()

# Get current holdings (short positions prefixed with "Short: ")
holdings = portfolio.get_current_holdings()
print(f"Holdings: {holdings}")

# Get portfolio value over time (shorts valued mark-to-market)
values = portfolio.get_portfolio_value(
    date(2023, 1, 1),
    date(2023, 12, 31)
)

# Get portfolio summary
summary = portfolio.get_portfolio_summary()
print(f"Total Value: {summary['total_value']:,.2f} {summary['currency']}")
```

## CSV Format

**Delimiter:** Semicolon (`;`)

**Required columns:**

| Column | Type    | Description               |
|--------|---------|---------------------------|
| Date   | YYYY-MM-DD | Transaction date       |
| Ticker | String  | Stock ticker symbol       |
| Type   | Buy/Sell/Short/Cover | Transaction type |
| Amount | Integer | Number of shares          |
| Price  | Number  | Price per share           |

**Transaction type effects:**

| Type  | Shares      | Cash                    |
|-------|-------------|-------------------------|
| Buy   | +shares     | −(shares × price)       |
| Sell  | −shares     | +(shares × price)       |
| Short | −shares     | +(shares × price)       |
| Cover | +shares     | −(shares × price)       |

**Example:**
```csv
Date;Ticker;Type;Amount;Price
2023-01-15;AAPL;Buy;10;150.50
2023-02-20;MSFT;Buy;5;250.75
2023-03-10;AAPL;Sell;5;165.25
2023-04-05;TSLA;Buy;2;800.00
2023-06-01;NVDA;Short;4;420.00
2023-11-01;NVDA;Cover;4;460.00
```

## Documentation

### Core Methods

#### `FinTrack.__init__(initial_cash, currency, csv_file, user_id=None)`
Initialize a portfolio tracker.

**Parameters:**
- `initial_cash`: Starting cash amount (must be non-negative)
- `currency`: Base currency code (3-letter code, e.g., 'USD', 'EUR')
- `csv_file`: Path to transactions CSV file
- `user_id`: Optional identifier for multi-user setups (default: 'default')

**Raises:**
- `FileNotFoundError`: If CSV file doesn't exist
- `ValidationError`: If parameters are invalid

#### `get_current_holdings() -> List[str]`
Get list of current stock holdings with company names. Short positions are prefixed with `"Short: "`.

#### `get_portfolio_value(from_date, to_date) -> Dict[date, float]`
Get portfolio value for each day in date range.

For short positions, value = cash (including short proceeds) + (negative_shares × current_price), which equals the unrealized P&L on the short automatically.

#### `get_portfolio_cash(date) -> Optional[float]`
Get cash balance on specific date. Cash includes proceeds received from short sales.

#### `get_portfolio_summary() -> Dict`
Get comprehensive portfolio summary. Holdings include an `is_short` boolean field. Short positions show negative `shares` and `value`.

#### `get_stock_returns(from_date, to_date) -> Dict[str, float]`
Calculate returns for each stock held during the period, including short positions.

- **Long positions**: standard return on invested capital
- **Short positions**: return = (proceeds − cover cost) / cover cost
- **Mixed activity**: Modified Dietz-style approach

**Returns:** Dictionary mapping ticker symbols to returns (e.g., 0.062 = 6.2%, −0.05 = −5%)

#### `print_stock_returns(from_date, to_date, sort_by='return')`
Print a formatted table of stock returns. Open short positions are labelled with `(Short)`.

#### `get_index_returns(ticker, start_date, end_date) -> List[float]`
Get daily returns for a benchmark index relative to start price.

#### `update_portfolio()`
Refresh portfolio with latest data from Yahoo Finance.

### Short Selling — How It Works

#### Opening a short (`Type=Short`)
- Holdings for that ticker decrease by the shorted amount (goes negative)
- Cash increases by `shares × price` (simplified — proceeds credited immediately)
- Prices are fetched for the ticker throughout the short period

#### Closing a short (`Type=Cover`)
- Holdings for that ticker increase by the covered amount (back toward zero)
- Cash decreases by `shares × price` (cost to buy back)

#### Daily valuation of open shorts
Because short proceeds were already credited to cash, the portfolio value calculation is:

```
value = cash + Σ(shares × price)
```

Since shorted shares are negative, their contribution is negative — i.e., the current cost-to-cover is subtracted from cash. The net result is the unrealized P&L:

```
unrealized P&L = proceeds_received − current_cost_to_cover
```

**Example:** Short 10 shares of TSLA at $300 → cash +$3,000. If today's price is $260:
```
contribution = -10 × $260 = -$2,600
net = $3,000 (cash) - $2,600 = +$400 unrealized gain ✓
```

### Configuration

Data is stored in user's home directory:
```
~/.fintrack/
├── default/                    # Default user
│   └── data/
│       └── portfolio.db       # Portfolio database
├── user123/                    # Custom user
│   └── data/
│       └── portfolio.db
└── logs/
    └── fintrack.log           # Activity log
```

### Logging

```python
from FinTrack import setup_logger, get_logger
import logging

logger = setup_logger("my_app", level=logging.DEBUG)
logger.info("Portfolio initialized")
```

Logs are written to `~/.fintrack/logs/fintrack.log` by default.

### Error Handling

```python
from FinTrack import (
    FinTrackError,
    ValidationError,
    DataFetchError,
    PriceError,
    DatabaseError,
    ConfigError,
)

try:
    portfolio = FinTrack(150000, "USD", "transactions.csv")
except ValidationError as e:
    print(f"Invalid input: {e}")
except FinTrackError as e:
    print(f"FinTrack error: {e}")
```

### Input Validation

```python
from FinTrack import TransactionValidator

df = pd.read_csv("transactions.csv", sep=";")
is_valid, errors = TransactionValidator.validate_dataframe(df)

if not is_valid:
    for error in errors:
        print(f"  - {error}")
```

Validation checks:
- ✓ Date format (YYYY-MM-DD)
- ✓ Ticker symbols (non-empty)
- ✓ Transaction type (Buy, Sell, Short, or Cover)
- ✓ Amount (positive integer)
- ✓ Price (positive number)

## How It Works

### Database Structure

FinTrack uses SQLite with three main tables:

1. **portfolio**: Holdings per date (positive = long, negative = short)
2. **cash**: Cash balance tracking (includes short sale proceeds)
3. **prices**: Daily stock prices in base currency (fetched for all open positions)

### Price Management

- Prices automatically fetched from Yahoo Finance for all non-zero positions (long and short)
- Multi-currency portfolios: prices converted to base currency
- Forward-filling for missing trading days
- Custom prices from CSV supported

### Cash Flow Tracking

| Event          | Cash effect     |
|----------------|-----------------|
| Buy stock      | Decreases       |
| Sell stock     | Increases       |
| Short stock    | Increases       |
| Cover short    | Decreases       |
| Dividend       | Increases (long positions only) |

### Stock Returns Calculation

Returns use a Modified Dietz approach treating all cash outflows (Buy, Cover) and inflows (Sell, Short) consistently, giving accurate performance metrics regardless of position type or how many times shares changed hands during the period.

## Supported Currencies

```python
portfolio = FinTrack(100000, "USD")  # US Dollar
portfolio = FinTrack(100000, "EUR")  # Euro
portfolio = FinTrack(100000, "GBP")  # British Pound
portfolio = FinTrack(100000, "JPY")  # Japanese Yen
portfolio = FinTrack(100000, "SEK")  # Swedish Krona
```

## Requirements

- Python >= 3.8
- pandas >= 1.3.0
- yfinance >= 0.2.0

## Development

### Running Tests

```bash
pytest tests/
pytest tests/ --cov=src/FinTrack --cov-report=html
pytest tests/test_validation.py
```

### Code Quality

```bash
black src/
flake8 src/
mypy src/
```

## Limitations

- Prices fetched from Yahoo Finance — verify data quality
- Daily resolution only (intra-day trading not supported)
- Short selling uses a simplified cash model (proceeds credited immediately, no margin requirements)
- Corporate actions (stock splits, mergers) must be manually adjusted
- Past dividend data depends on Yahoo Finance records

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License — see [LICENSE](LICENSE) for details.

## Disclaimer

This software is provided as-is for educational and informational purposes. Always verify your portfolio calculations independently. The short selling implementation uses a simplified cash model and does not account for margin requirements, borrowing costs, or broker-specific rules. The author is not responsible for any financial losses resulting from use of this software.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

## Support

- [GitHub Issues](https://github.com/arofredriksson/FinTrack/issues)
- Email: arofre903@gmail.com

## Version History

- **v1.2.0** (2026-02-18): Short selling support (Short/Cover transaction types, mark-to-market valuation)
- **v1.1.1** (2026-02-15): Added stock returns analysis methods and improved index returns handling
- **v1.1.0** (2026-02-14): Major refactoring with full test suite, proper error handling, logging, and pandas 2.0 compatibility
- **v1.0.0** (2026-02-13): Initial release

---

**Built by:** Aron Fredriksson  
**License:** MIT  
**Last Updated:** February 2026
