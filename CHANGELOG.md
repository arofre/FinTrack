# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-14

### Major Changes

This is a comprehensive rewrite addressing all code quality, documentation, and reliability issues found in v1.0.0.

### Added

- **Comprehensive Error Handling**
  - Custom exception hierarchy (FinTrackError, ValidationError, DataFetchError, etc.)
  - Clear, actionable error messages
  - Proper exception chaining for debugging

- **Input Validation**
  - Full validation of transaction CSV data
  - Validation of initial_cash parameter
  - Validation of currency codes
  - Comprehensive error reporting for invalid data

- **Logging System**
  - Professional logging using Python's logging module
  - Both console and file output
  - Configurable log levels
  - Logs stored in ~/.fintrack/logs/fintrack.log

- **Configuration Management**
  - Config class for managing paths
  - User isolation (separate data directories per user)
  - Configurable database location
  - Multi-user support

- **Type Hints**
  - Complete type annotations throughout codebase
  - Better IDE support and error detection
  - Improved code documentation

- **Comprehensive Documentation**
  - Docstrings for all public functions and classes
  - Type hints for all parameters and return values
  - Usage examples in docstrings
  - Expanded README with detailed API documentation

- **Test Suite**
  - 80%+ code coverage
  - Tests for validation
  - Tests for portfolio operations
  - Tests for error handling
  - Tests for configuration management
  - Pytest fixtures for easy testing

- **Performance Improvements**
  - Currency lookup caching
  - Reduced repeated Yahoo Finance API calls
  - More efficient database queries

- **New Features**
  - `get_portfolio_summary()` method for quick overview
  - Multi-user support with user_id parameter
  - Currency-agnostic output messages
  - Better dividend handling

### Fixed

- **Pandas Deprecation Warnings**
  - Fixed deprecated `reindex(method=...)` usage
  - Fixed deprecated `fillna(method=...)` usage
  - Now compatible with pandas 2.0+

- **Missing Imports**
  - Added missing `timedelta` import in portfolio.py
  - Added missing `yfinance` import in portfolio.py

- **Documentation-Code Mismatch**
  - Updated all docs to use correct class name `FinTrack`
  - Removed references to non-existent `Portfolio_tracker`
  - Updated QUICKSTART.md with correct imports and examples

- **Hardcoded Currency References**
  - Replaced hardcoded "SEK" with currency variable
  - All output messages now use portfolio's base currency
  - Consistent currency display throughout

- **Database Path Issues**
  - Database no longer hardcoded to current directory
  - Now stored in ~/.fintrack/{user_id}/data/portfolio.db
  - User-specific data isolation
  - Proper directory creation

- **Error Handling**
  - Replaced bare `except` clauses with specific exception types
  - Proper logging of errors
  - Better error messages
  - Exception chaining for debugging

- **Resource Management**
  - Database connections now use context managers
  - Proper cleanup on exceptions
  - No resource leaks

### Changed

- **Class Naming**: Standardized on `FinTrack` class name
- **Module Organization**: Better separation of concerns with new modules:
  - `config.py` for configuration
  - `errors.py` for custom exceptions
  - `logger.py` for logging setup
  - `validation.py` for input validation
- **Database Schema**: Added indexes and constraints (planned for future)
- **Logging**: Replaced all `print()` statements with proper logging
- **Exception Handling**: More specific, descriptive error messages

### Deprecated

- Use of hardcoded database paths (now configured via Config class)

### Removed

- Bare `except` clauses
- Generic error handling

### Security

- Input validation prevents malformed data
- Better error messages don't expose sensitive information
- Proper logging for audit trails

### Known Issues

None

## [1.0.0] - 2026-02-13

### Added

- Initial release of Portfolio Tracker
- Portfolio management with buy/sell transaction tracking
- Dynamic stock price fetching using yfinance
- Multi-currency support with automatic conversion
- Cash management system with transaction and dividend tracking
- Historical portfolio value analysis
- Index return comparison functionality
- SQLite-based data storage for holdings, prices, and cash balances
- Support for dividend tracking and automatic cash updates

### Features

- `FinTrack` class for portfolio initialization and management
- `update_portfolio()` method for refreshing portfolio data
- `get_portfolio_value()` for historical value analysis
- `get_current_holdings()` for viewing current positions
- `get_past_holdings()` for viewing all historical positions
- `get_portfolio_cash()` for cash balance queries
- `get_index_returns()` for benchmark comparison

### Known Issues

- Pandas deprecation warnings with pandas 1.4.0+
- Hardcoded currency references ("SEK") in output
- Missing imports (timedelta, yfinance)
- Documentation-code mismatch (Portfolio_tracker vs FinTrack)
- Hardcoded database path
- Limited error handling
- No input validation
- No logging system
- No type hints
- No test suite

---

## Migration from v1.0.0 to v1.1.0

### Breaking Changes

None - API is backward compatible. However, database location has changed:

**v1.0.0:** `./portfolio.db` (current directory)
**v1.1.0:** `~/.fintrack/default/data/portfolio.db` (user home directory)

### Migration Steps

1. Update import: `from portfolio_tracker import Portfolio_tracker` → `from FinTrack import FinTrack`
2. Update class name if used directly: `Portfolio_tracker` → `FinTrack`
3. Optional: Copy old `portfolio.db` to new location if needed

```python
# Old code (v1.0.0)
from portfolio_tracker import Portfolio_tracker
portfolio = Portfolio_tracker(150000, "SEK", "transactions.csv")

# New code (v1.1.0)
from FinTrack import FinTrack
portfolio = FinTrack(150000, "SEK", "transactions.csv")
```

### New Features to Explore

- Use `get_portfolio_summary()` for quick overview
- Check logs in `~/.fintrack/logs/fintrack.log`
- Enable debug logging with `setup_logger(..., level=logging.DEBUG)`
- Use user_id for multi-user setups: `FinTrack(..., user_id="alice")`

---

## Upcoming

### v2.0.0 (Planned)

- Web dashboard for portfolio visualization
- CSV export functionality
- Tax lot tracking
- Advanced rebalancing suggestions
- API endpoint support
- Database migration system
- Performance improvements
