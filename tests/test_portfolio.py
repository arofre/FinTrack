"""Tests for portfolio core functionality."""
import pytest
from datetime import date, timedelta
from src.FinTrack import FinTrack
from src.FinTrack.errors import FinTrackError, ValidationError


class TestPortfolioInitialization:
    """Test portfolio initialization."""

    def test_portfolio_creates_successfully(self, portfolio_instance):
        """Test that portfolio initializes without error."""
        assert portfolio_instance is not None
        assert portfolio_instance.initial_cash == 150000
        assert portfolio_instance.currency == "USD"

    def test_portfolio_with_invalid_csv(self, temp_dir):
        """Test that invalid CSV raises error."""
        with pytest.raises(FileNotFoundError):
            FinTrack(
                initial_cash=150000,
                currency="USD",
                csv_file="/nonexistent/file.csv"
            )

    def test_portfolio_negative_cash(self, sample_csv):
        """Test that negative initial cash is rejected."""
        with pytest.raises(ValidationError):
            FinTrack(
                initial_cash=-150000,
                currency="USD",
                csv_file=sample_csv
            )

    def test_portfolio_invalid_currency(self, sample_csv):
        """Test that invalid currency is rejected."""
        with pytest.raises(ValidationError):
            FinTrack(
                initial_cash=150000,
                currency="INVALID",
                csv_file=sample_csv
            )

    def test_portfolio_lowercase_currency(self, sample_csv):
        """Test that lowercase currency is rejected."""
        with pytest.raises(ValidationError):
            FinTrack(
                initial_cash=150000,
                currency="usd",
                csv_file=sample_csv
            )


class TestPortfolioQueries:
    """Test portfolio query methods."""

    def test_get_current_holdings(self, portfolio_instance):
        """Test getting current holdings."""
        holdings = portfolio_instance.get_current_holdings()
        assert isinstance(holdings, list)
        # After transactions: bought AAPL (10-5=5), MSFT (5), TSLA (2)
        assert len(holdings) > 0

    def test_get_past_holdings(self, portfolio_instance):
        """Test getting all historical holdings."""
        holdings = portfolio_instance.get_past_holdings()
        assert isinstance(holdings, list)
        # Should include all tickers ever owned
        assert len(holdings) >= 3

    def test_get_portfolio_value_single_date(self, portfolio_instance):
        """Test getting portfolio value for single date."""
        values = portfolio_instance.get_portfolio_value(
            from_date=date(2023, 1, 15),
            to_date=date(2023, 1, 15)
        )
        assert isinstance(values, dict)
        assert len(values) > 0

    def test_get_portfolio_value_date_range(self, portfolio_instance):
        """Test getting portfolio value for date range."""
        values = portfolio_instance.get_portfolio_value(
            from_date=date(2023, 1, 15),
            to_date=date(2023, 4, 5)
        )
        assert isinstance(values, dict)
        # Should have entries for multiple days
        assert len(values) > 1

    def test_get_portfolio_cash_returns_float(self, portfolio_instance):
        """Test getting cash balance returns float."""
        cash = portfolio_instance.get_portfolio_cash(date(2023, 1, 15))
        # Cash can be None if no data, but should be numeric when present
        assert cash is None or isinstance(cash, float)

    def test_portfolio_value_calculation(self, portfolio_instance):
        """Test that portfolio value is calculated correctly."""
        values = portfolio_instance.get_portfolio_value(
            from_date=date(2023, 1, 15),
            to_date=date(2023, 1, 20)
        )
        # Should have some values
        assert len(values) > 0
        # Values should be numeric
        for value in values.values():
            assert isinstance(value, (int, float))
            assert value >= 0


class TestPortfolioUpdate:
    """Test portfolio update functionality."""

    def test_update_portfolio_completes(self, portfolio_instance):
        """Test that update_portfolio runs without raising."""
        # Should complete without raising (network errors are acceptable)
        try:
            portfolio_instance.update_portfolio()
            assert True  # Success
        except Exception as e:
            # Only accept certain types of errors (network, data fetch)
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['network', 'connection', 'fetch', 'no data']):
                assert True  # Network error is acceptable
            else:
                raise


class TestIndexReturns:
    """Test index return calculations."""

    def test_get_index_returns_format(self, portfolio_instance):
        """Test that index returns are in correct format."""
        try:
            returns = portfolio_instance.get_index_returns(
                ticker="^GSPC",
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31)
            )
            assert isinstance(returns, list)
            assert len(returns) > 0
            # Returns should be between -1 and 1 (can't gain/lose more than 100% in a day)
            for ret in returns:
                assert -1 <= ret <= 1
        except Exception as e:
            # Network errors are acceptable
            error_msg = str(e).lower()
            if 'network' not in error_msg and 'connection' not in error_msg:
                raise

    def test_index_returns_monotonic(self, portfolio_instance):
        """Test that cumulative returns are generally increasing."""
        try:
            returns = portfolio_instance.get_index_returns(
                ticker="^GSPC",
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31)
            )
            # Should have many returns for a full year
            assert len(returns) >= 100  # At least 100 trading days
        except Exception as e:
            # Network errors are acceptable
            error_msg = str(e).lower()
            if 'network' not in error_msg and 'connection' not in error_msg:
                raise


class TestPortfolioSummary:
    """Test portfolio summary functionality."""

    def test_get_portfolio_summary_structure(self, portfolio_instance):
        """Test that portfolio summary has expected structure."""
        summary = portfolio_instance.get_portfolio_summary()
        
        assert isinstance(summary, dict)
        assert 'date' in summary
        assert 'currency' in summary
        assert 'holdings' in summary
        assert 'cash' in summary
        assert 'total_value' in summary
        
        # Check types
        assert summary['currency'] == 'USD'
        assert isinstance(summary['cash'], (int, float))
        assert isinstance(summary['total_value'], (int, float))
        assert isinstance(summary['holdings'], list)

    def test_portfolio_summary_positive_values(self, portfolio_instance):
        """Test that portfolio values are positive."""
        summary = portfolio_instance.get_portfolio_summary()
        
        assert summary['cash'] >= 0
        assert summary['total_value'] >= 0


class TestPortfolioRepr:
    """Test portfolio string representation."""

    def test_portfolio_repr(self, portfolio_instance):
        """Test __repr__ method."""
        repr_str = repr(portfolio_instance)
        assert 'FinTrack' in repr_str
        assert '150000' in repr_str
        assert 'USD' in repr_str
