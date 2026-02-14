"""Configuration management for FinTrack."""
import os
from pathlib import Path
from typing import Optional


class Config:
    """FinTrack configuration management."""

    @staticmethod
    def get_data_dir(user_id: Optional[str] = None) -> Path:
        """
        Get the data directory for storing portfolio data.

        Args:
            user_id: Optional user identifier. If not provided, uses default.

        Returns:
            Path to data directory

        Example:
            >>> data_dir = Config.get_data_dir("user123")
            >>> data_dir
            PosixPath('/home/user/.fintrack/user123/data')
        """
        if user_id is None:
            user_id = "default"

        data_dir = Path.home() / ".fintrack" / user_id / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @staticmethod
    def get_db_path(user_id: Optional[str] = None) -> str:
        """
        Get the database file path.

        Args:
            user_id: Optional user identifier.

        Returns:
            String path to portfolio database file
        """
        data_dir = Config.get_data_dir(user_id)
        return str(data_dir / "portfolio.db")

    @staticmethod
    def get_logs_dir() -> Path:
        """
        Get the logs directory.

        Returns:
            Path to logs directory
        """
        logs_dir = Path.home() / ".fintrack" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    @staticmethod
    def get_log_file() -> str:
        """
        Get the main log file path.

        Returns:
            String path to main log file
        """
        return str(Config.get_logs_dir() / "fintrack.log")
