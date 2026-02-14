# FinTrack - Advanced Portfolio Tracker

[![Tests](https://img.shields.io/badge/tests-passing-green)](./tests)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A Python package for tracking and analyzing stock portfolios with multi-currency support and automatic dividend tracking.

## Important note

Tests, instructions and docstrings written using Claude, I tried to find any incorrect information but some may have slipped through the crack. 

## Features

- **Portfolio Management**: Track multiple stock holdings with buy/sell transactions
- **Dynamic Price Tracking**: Automatically fetch and store historical stock prices using yfinance
- **Multi-Currency Support**: Handle stocks traded in different currencies with automatic conversion
- **Cash Management**: Maintain accurate cash balances accounting for buy/sell transactions and dividend payments
- **Dividend Tracking**: Automatically capture and account for dividend payments
- **Historical Analysis**: Query portfolio composition and value at any point in time
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

# Get current holdings
holdings = portfolio.get_current_holdings()
print(f"Holdings: {holdings}")

# Get portfolio value over time
values = portfolio.get_portfolio_value(
    date(2023, 1, 1),
    date(2023, 12, 31)
)

# Get portfolio summary
summary = portfolio.get_portfolio_summary()
print(f"Total Value: {summary['total_value']:,.2f} {summary['currency']}")
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
Get list of current stock holdings with company names.

#### `get_portfolio_value(from_date, to_date) -> Dict[date, float]`
Get portfolio value for each day in date range.

#### `get_portfolio_cash(date) -> Optional[float]`
Get cash balance on specific date.

#### `get_portfolio_summary() -> Dict`
Get comprehensive portfolio summary including:
- Current holdings with prices and values
- Cash balance
- Total portfolio value

#### `get_index_returns(ticker, start_date, end_date) -> List[float]`
Get daily returns for a benchmark index.

#### `update_portfolio()`
Refresh portfolio with latest data from Yahoo Finance.

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

Access paths programmatically:
```python
from FinTrack import Config

data_dir = Config.get_data_dir("user123")
db_path = Config.get_db_path("user123")
logs_dir = Config.get_logs_dir()
```

### Logging

FinTrack uses Python's standard logging module:

```python
from FinTrack import setup_logger, get_logger
import logging

# Set up with custom level
logger = setup_logger("my_app", level=logging.DEBUG)

# Or get existing logger
logger = get_logger(__name__)

logger.info("Portfolio initialized")
logger.debug("Detailed debug information")
logger.warning("Warning about something")
logger.error("An error occurred")
```

Logs are written to `~/.fintrack/logs/fintrack.log` by default.

### Error Handling

FinTrack provides specific exception types:

```python
from FinTrack import (
    FinTrackError,        # Base exception
    ValidationError,      # Input validation failed
    DataFetchError,       # Yahoo Finance fetch failed
    PriceError,          # Price data unavailable
    DatabaseError,       # Database operation failed
    ConfigError          # Configuration issue
)

try:
    portfolio = FinTrack(150000, "USD", "transactions.csv")
except ValidationError as e:
    print(f"Invalid input: {e}")
except FinTrackError as e:
    print(f"FinTrack error: {e}")
```

### Input Validation

All transaction data is automatically validated:

```python
from FinTrack import TransactionValidator, ValidationError

df = pd.read_csv("transactions.csv", sep=";")
is_valid, errors = TransactionValidator.validate_dataframe(df)

if not is_valid:
    for error in errors:
        print(f"  - {error}")
```

Validation checks:
- ✓ Date format (YYYY-MM-DD)
- ✓ Ticker symbols (non-empty, alphanumeric)
- ✓ Transaction type (Buy or Sell)
- ✓ Amount (positive integer)
- ✓ Price (positive number)

## CSV Format

**Delimiter:** Semicolon (`;`)

**Required columns:**
| Column | Type | Description |
|--------|------|-------------|
| Date | YYYY-MM-DD | Transaction date |
| Ticker | String | Stock ticker symbol |
| Type | Buy/Sell | Transaction type |
| Amount | Integer | Number of shares |
| Price | Number | Price per share |

**Optional columns:**
- Custom price specifications (to override Yahoo Finance data)
- Additional metadata

**Example:**
```csv
Date;Ticker;Type;Amount;Price
2023-01-15;AAPL;Buy;10;150.50
2023-02-20;MSFT;Buy;5;250.75
2023-03-10;AAPL;Sell;5;165.25
2023-04-05;TSLA;Buy;2;800.00
```

## How It Works

### Database Structure

FinTrack uses SQLite with three main tables:

1. **portfolio**: Holdings for each date
2. **cash**: Cash balance tracking
3. **prices**: Daily stock prices in base currency

### Price Management

- Prices automatically fetched from Yahoo Finance
- Multi-currency portfolios: prices converted to base currency
- Forward-filling for missing trading days
- Custom prices from CSV supported

### Cash Flow Tracking

Cash balance updated for:
- Stock purchases (deduct)
- Stock sales (add)
- Dividend payments (add)

## Supported Currencies

Works with any currency pair available on Yahoo Finance:

```python
# Major currencies
portfolio = FinTrack(100000, "USD")  # US Dollar
portfolio = FinTrack(100000, "EUR")  # Euro
portfolio = FinTrack(100000, "GBP")  # British Pound
portfolio = FinTrack(100000, "JPY")  # Japanese Yen
portfolio = FinTrack(100000, "SEK")  # Swedish Krona

# Emerging markets and others available
portfolio = FinTrack(100000, "INR")  # Indian Rupee
portfolio = FinTrack(100000, "BRL")  # Brazilian Real
```

## Requirements

- Python >= 3.8
- pandas >= 1.3.0
- yfinance >= 0.2.0

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=src/FinTrack --cov-report=html

# Specific test file
pytest tests/test_validation.py

# Specific test
pytest tests/test_validation.py::TestTransactionValidator::test_valid_transaction_row
```

### Code Quality

```bash
# Format code
black src/

# Lint
flake8 src/

# Type checking
mypy src/
```

## Limitations

- Prices are fetched from Yahoo Finance; verify data quality
- Daily resolution only (intra-day trading not supported)
- Corporate actions (stock splits, mergers) must be manually adjusted
- Past dividend data depends on Yahoo Finance records

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Disclaimer

This software is provided as-is for educational and informational purposes. Always verify your portfolio calculations independently. The author is not responsible for any financial losses resulting from use of this software.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

## Support

For issues, questions, or suggestions:
- [GitHub Issues](https://github.com/arofredriksson/FinTrack/issues)
- Email: arofre903@gmail.com

## Version History

- **v1.1.0** (2026): Major refactoring with full test suite, proper error handling, logging, and pandas 2.0 compatibility
- **v1.0.0** (2026): Initial release

---

**Built by:** Aron Fredriksson  
**License:** MIT  
**Last Updated:** 2026
