"""Tests for transaction validation."""
import pytest
import pandas as pd
from src.FinTrack.validation import TransactionValidator, ValidationError
from src.FinTrack.validation import validate_initial_cash, validate_currency


class TestTransactionValidator:
    """Test transaction validation logic."""

    def test_valid_transaction_row(self):
        """Test that valid transaction passes validation."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': 'AAPL',
            'Type': 'Buy',
            'Amount': 10,
            'Price': 150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert len(errors) == 0

    def test_invalid_date_format(self):
        """Test that invalid date is caught."""
        row = pd.Series({
            'Date': 'not-a-date',
            'Ticker': 'AAPL',
            'Type': 'Buy',
            'Amount': 10,
            'Price': 150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert any('date' in e.lower() for e in errors)

    def test_negative_amount(self):
        """Test that negative amount is rejected."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': 'AAPL',
            'Type': 'Buy',
            'Amount': -10,
            'Price': 150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert any('positive' in e.lower() for e in errors)

    def test_zero_amount(self):
        """Test that zero amount is rejected."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': 'AAPL',
            'Type': 'Buy',
            'Amount': 0,
            'Price': 150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert any('positive' in e.lower() for e in errors)

    def test_invalid_type(self):
        """Test that invalid transaction type is rejected."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': 'AAPL',
            'Type': 'Invalid',
            'Amount': 10,
            'Price': 150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert any('buy' in e.lower() or 'sell' in e.lower() for e in errors)

    def test_negative_price(self):
        """Test that negative price is rejected."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': 'AAPL',
            'Type': 'Buy',
            'Amount': 10,
            'Price': -150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert any('negative' in e.lower() for e in errors)

    def test_zero_price(self):
        """Test that zero price is rejected."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': 'AAPL',
            'Type': 'Buy',
            'Amount': 10,
            'Price': 0
        })
        errors = TransactionValidator.validate_row(row)
        assert len(errors) > 0

    def test_missing_ticker(self):
        """Test that missing ticker is rejected."""
        row = pd.Series({
            'Date': '2023-01-15',
            'Ticker': '',
            'Type': 'Buy',
            'Amount': 10,
            'Price': 150.00
        })
        errors = TransactionValidator.validate_row(row)
        assert any('ticker' in e.lower() for e in errors)

    def test_valid_dataframe(self, sample_dataframe):
        """Test validation of entire dataframe."""
        is_valid, errors = TransactionValidator.validate_dataframe(sample_dataframe)
        assert is_valid is True
        assert len(errors) == 0

    def test_dataframe_missing_columns(self):
        """Test that missing columns are detected."""
        df = pd.DataFrame({
            'Date': ['2023-01-15'],
            'Ticker': ['AAPL'],
        })
        is_valid, errors = TransactionValidator.validate_dataframe(df)
        assert is_valid is False
        assert any('Missing' in e for e in errors)


class TestParameterValidation:
    """Test parameter validation functions."""

    def test_valid_initial_cash(self):
        """Test that valid initial cash passes."""
        validate_initial_cash(150000)  # Should not raise

    def test_negative_initial_cash(self):
        """Test that negative cash is rejected."""
        with pytest.raises(ValidationError):
            validate_initial_cash(-150000)

    def test_zero_initial_cash(self):
        """Test that zero cash is allowed (but warned about)."""
        validate_initial_cash(0)  # Should not raise

    def test_invalid_initial_cash_type(self):
        """Test that non-numeric cash is rejected."""
        with pytest.raises(ValidationError):
            validate_initial_cash("150000")

    def test_valid_currency(self):
        """Test that valid currency passes."""
        validate_currency("USD")  # Should not raise

    def test_invalid_currency_length(self):
        """Test that non-3-character currency is rejected."""
        with pytest.raises(ValidationError):
            validate_currency("US")

    def test_invalid_currency_lowercase(self):
        """Test that lowercase currency is rejected."""
        with pytest.raises(ValidationError):
            validate_currency("usd")

    def test_invalid_currency_type(self):
        """Test that non-string currency is rejected."""
        with pytest.raises(ValidationError):
            validate_currency(123)
