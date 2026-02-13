# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-02-13

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
- `Portfolio_tracker` class for portfolio initialization and management
- `update_portfolio()` method for refreshing portfolio data
- `get_portfolio_value()` for historical value analysis
- `get_current_holdings()` for viewing current positions
- `get_past_holdings()` for viewing all historical positions
- `get_portfolio_cash()` for cash balance queries
- `get_index_returns()` for benchmark comparison

## [Unreleased]

### Planned
- Web dashboard for portfolio visualization
- Performance analytics and reporting
- Tax lot tracking
- Advanced rebalancing suggestions
- API for programmatic portfolio updates
- CSV export of holdings and performance data
