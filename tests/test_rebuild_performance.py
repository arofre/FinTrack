"""Tests for rebuild behavior on larger datasets."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.FinTrack import FinTrack, config
from src.FinTrack.parsing_tools import build_holding_table, get_portfolio


def _patch_data_dir(monkeypatch, base_dir: Path) -> None:
    def mock_get_data_dir(user_id=None):
        data_dir = base_dir / (user_id or "default") / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    monkeypatch.setattr(config.Config, "get_data_dir", staticmethod(mock_get_data_dir))


def test_build_holding_table_large_dataset_preserves_holdings(tmp_path, monkeypatch):
    """Large transaction files should rebuild holdings correctly."""
    _patch_data_dir(monkeypatch, tmp_path)

    start = date.today() - timedelta(days=120)
    tickers = [f"TICK{i:02d}" for i in range(20)]
    rows = []

    for day_offset in range(120):
        d = start + timedelta(days=day_offset)
        for ticker_idx, ticker in enumerate(tickers):
            tx_type = "Buy" if (day_offset + ticker_idx) % 2 == 0 else "Sell"
            rows.append(
                {
                    "Date": d.isoformat(),
                    "Ticker": ticker,
                    "Type": tx_type,
                    "Amount": 1,
                    "Price": 100 + ticker_idx,
                }
            )

    csv_path = tmp_path / "large_transactions.csv"
    pd.DataFrame(rows).to_csv(csv_path, sep=";", index=False)

    build_holding_table(str(csv_path), user_id="loadtest")

    expected = (
        pd.DataFrame(rows)
        .assign(
            SignedAmount=lambda df: df["Amount"]
            * df["Type"].map({"Buy": 1, "Cover": 1, "Sell": -1, "Short": -1})
        )
        .groupby("Ticker")["SignedAmount"]
        .sum()
    )
    expected_dict = {ticker: int(value) for ticker, value in expected.items() if value != 0}

    holdings = get_portfolio(date.today(), user_id="loadtest")
    assert holdings == expected_dict

    db_path = config.Config.get_db_path("loadtest")
    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM portfolio").fetchone()[0]

    assert row_count == 120


def test_rebuild_avoids_full_portfolio_materialization_and_is_idempotent(tmp_path, monkeypatch):
    """Rebuild/update path should avoid SELECT * portfolio scans and remain idempotent."""
    _patch_data_dir(monkeypatch, tmp_path)

    today = date.today()
    csv_path = tmp_path / "transactions.csv"
    pd.DataFrame(
        [
            {"Date": (today - timedelta(days=4)).isoformat(), "Ticker": "AAPL", "Type": "Buy", "Amount": 3, "Price": 100.0},
            {"Date": (today - timedelta(days=2)).isoformat(), "Ticker": "MSFT", "Type": "Buy", "Amount": 2, "Price": 200.0},
            {"Date": (today - timedelta(days=1)).isoformat(), "Ticker": "AAPL", "Type": "Sell", "Amount": 1, "Price": 110.0},
        ]
    ).to_csv(csv_path, sep=";", index=False)

    import src.FinTrack.parsing_tools as parsing_tools

    original_read_sql_query = parsing_tools.pd.read_sql_query
    seen_queries = []

    def tracking_read_sql_query(query, *args, **kwargs):
        seen_queries.append(" ".join(str(query).split()))
        return original_read_sql_query(query, *args, **kwargs)

    def fake_download(_ticker, start=None, end=None, auto_adjust=False, progress=False):
        del auto_adjust, progress
        idx = pd.date_range(start=start, end=end - timedelta(days=1), freq="D")
        if len(idx) == 0:
            return pd.DataFrame()
        return pd.DataFrame({"Close": [100.0] * len(idx)}, index=idx)

    monkeypatch.setattr(parsing_tools.pd, "read_sql_query", tracking_read_sql_query)
    monkeypatch.setattr(parsing_tools, "get_currency_from_ticker", lambda _ticker: "USD")
    monkeypatch.setattr(parsing_tools, "get_dividends", lambda *_args, **_kwargs: pd.Series(dtype=float))
    monkeypatch.setattr(parsing_tools.yf, "download", fake_download)

    portfolio = FinTrack(initial_cash=10000, currency="USD", csv_file=str(csv_path), user_id="worker")

    db_path = config.Config.get_db_path("worker")
    with sqlite3.connect(db_path) as conn:
        prices_before = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        cash_before = conn.execute("SELECT COUNT(*) FROM cash").fetchone()[0]

    portfolio.update_portfolio()

    with sqlite3.connect(db_path) as conn:
        prices_after = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        cash_after = conn.execute("SELECT COUNT(*) FROM cash").fetchone()[0]

    assert all("SELECT * FROM portfolio" not in query for query in seen_queries)
    assert prices_after == prices_before
    assert cash_after == cash_before
