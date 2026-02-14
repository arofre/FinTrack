"""Input validation for FinTrack transactions and data."""
from typing import List, Tuple

import pandas as pd

from .errors import ValidationError
from .logger import get_logger

logger = get_logger(__name__)


class TransactionValidator:
    """Validates transaction data from CSV files."""

    REQUIRED_COLUMNS = {"Date", "Ticker", "Type", "Amount", "Price"}
    VALID_TYPES = {"Buy", "Sell"}

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate entire transaction dataframe.

        Args:
            df: DataFrame with transaction data

        Returns:
            Tuple of (is_valid, list_of_errors)

        Example:
            >>> df = pd.DataFrame({...})
            >>> is_valid, errors = TransactionValidator.validate_dataframe(df)
            >>> if not is_valid:
            ...     raise ValidationError(f"Invalid data: {errors}")
        """
        errors = []

        # Check required columns
        missing_cols = cls.REQUIRED_COLUMNS - set(df.columns)
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return False, errors

        # Validate each row
        for idx, row in df.iterrows():
            row_errors = cls.validate_row(row)
            for error in row_errors:
                errors.append(f"Row {idx + 2}: {error}")

        return len(errors) == 0, errors

    @classmethod
    def validate_row(cls, row: pd.Series) -> List[str]:
        """
        Validate a single transaction row.

        Args:
            row: Series containing transaction data

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate Date
        if "Date" not in row:
            errors.append("Missing Date column")
        else:
            try:
                pd.to_datetime(row["Date"])
            except (ValueError, TypeError):
                errors.append(f"Invalid date format: {row['Date']} (expected YYYY-MM-DD)")

        # Validate Ticker
        if "Ticker" not in row:
            errors.append("Missing Ticker column")
        else:
            ticker = str(row["Ticker"]).strip()
            if not ticker or len(ticker) == 0:
                errors.append(f"Invalid ticker: empty or null")

        # Validate Type
        if "Type" not in row:
            errors.append("Missing Type column")
        else:
            if row["Type"] not in cls.VALID_TYPES:
                errors.append(
                    f"Type must be 'Buy' or 'Sell', got: {row['Type']}"
                )

        # Validate Amount
        if "Amount" not in row:
            errors.append("Missing Amount column")
        else:
            try:
                amount = float(row["Amount"])
                if amount <= 0:
                    errors.append(f"Amount must be positive, got: {amount}")
                elif not amount.is_integer() or amount < 0:
                    errors.append(f"Amount must be a positive integer, got: {amount}")
            except (ValueError, TypeError):
                errors.append(f"Invalid amount: {row['Amount']} (must be a number)")

        # Validate Price
        if "Price" not in row:
            errors.append("Missing Price column")
        else:
            try:
                price = float(row["Price"])
                if price < 0:
                    errors.append(f"Price cannot be negative, got: {price}")
                elif price == 0:
                    errors.append(f"Price cannot be zero")
            except (ValueError, TypeError):
                errors.append(f"Invalid price: {row['Price']} (must be a number)")

        return errors


def validate_initial_cash(initial_cash: int) -> None:
    """
    Validate initial cash amount.

    Args:
        initial_cash: Initial cash amount

    Raises:
        ValidationError: If initial_cash is invalid
    """
    if not isinstance(initial_cash, (int, float)):
        raise ValidationError(f"initial_cash must be a number, got: {type(initial_cash)}")
    if initial_cash < 0:
        raise ValidationError(f"initial_cash cannot be negative, got: {initial_cash}")
    if initial_cash == 0:
        logger.warning("initial_cash is 0 - portfolio will start with no cash")


def validate_currency(currency: str) -> None:
    """
    Validate currency code format.

    Args:
        currency: Currency code (e.g., 'USD', 'EUR')

    Raises:
        ValidationError: If currency format is invalid
    """
    if not isinstance(currency, str):
        raise ValidationError(f"currency must be a string, got: {type(currency)}")
    if len(currency) != 3:
        raise ValidationError(f"currency must be 3 characters, got: {currency}")
    if not currency.isupper():
        raise ValidationError(f"currency must be uppercase, got: {currency}")
