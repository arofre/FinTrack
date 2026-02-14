"""Pytest configuration and shared fixtures."""
import os
import pytest
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta

# Add src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def temp_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_csv(temp_dir):
    """Create sample transactions CSV."""
    csv_path = os.path.join(temp_dir, 'transactions.csv')
    csv_data = """Date;Ticker;Type;Amount;Price
2023-01-15;AAPL;Buy;10;150.00
2023-02-20;MSFT;Buy;5;250.00
2023-03-10;AAPL;Sell;5;165.00
2023-04-05;TSLA;Buy;2;800.00"""

    with open(csv_path, 'w') as f:
        f.write(csv_data)

    return csv_path


@pytest.fixture
def portfolio_instance(sample_csv, temp_dir, monkeypatch):
    """Create a FinTrack portfolio instance for testing."""
    # Mock the Config to use temp directory
    from src.FinTrack import config
    
    original_get_data_dir = config.Config.get_data_dir
    
    def mock_get_data_dir(user_id=None):
        data_dir = Path(temp_dir) / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    monkeypatch.setattr(config.Config, 'get_data_dir', staticmethod(mock_get_data_dir))
    
    from src.FinTrack import FinTrack
    portfolio = FinTrack(
        initial_cash=150000,
        currency="USD",
        csv_file=sample_csv
    )
    return portfolio


@pytest.fixture
def sample_dataframe():
    """Create sample transaction dataframe."""
    return pd.DataFrame({
        'Date': ['2023-01-15', '2023-02-20', '2023-03-10'],
        'Ticker': ['AAPL', 'MSFT', 'AAPL'],
        'Type': ['Buy', 'Buy', 'Sell'],
        'Amount': [10, 5, 5],
        'Price': [150.00, 250.00, 165.00]
    })


@pytest.fixture
def invalid_csv(temp_dir):
    """Create invalid transactions CSV."""
    csv_path = os.path.join(temp_dir, 'invalid.csv')
    csv_data = """Date;Ticker;Type;Amount;Price
invalid-date;AAPL;Buy;10;150.00
2023-02-20;MSFT;Invalid;5;250.00
2023-03-10;AAPL;Sell;-5;165.00"""

    with open(csv_path, 'w') as f:
        f.write(csv_data)

    return csv_path
