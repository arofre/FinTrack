"""Tests for error handling and configuration."""
import pytest
from pathlib import Path
from src.FinTrack.errors import (
    FinTrackError, ValidationError, DataFetchError,
    PriceError, DatabaseError, ConfigError
)
from src.FinTrack.config import Config


class TestCustomExceptions:
    """Test custom exception hierarchy."""

    def test_validation_error_is_fintrack_error(self):
        """Test that ValidationError is subclass of FinTrackError."""
        assert issubclass(ValidationError, FinTrackError)

    def test_data_fetch_error_is_fintrack_error(self):
        """Test that DataFetchError is subclass of FinTrackError."""
        assert issubclass(DataFetchError, FinTrackError)

    def test_price_error_is_fintrack_error(self):
        """Test that PriceError is subclass of FinTrackError."""
        assert issubclass(PriceError, FinTrackError)

    def test_database_error_is_fintrack_error(self):
        """Test that DatabaseError is subclass of FinTrackError."""
        assert issubclass(DatabaseError, FinTrackError)

    def test_config_error_is_fintrack_error(self):
        """Test that ConfigError is subclass of FinTrackError."""
        assert issubclass(ConfigError, FinTrackError)

    def test_raise_validation_error(self):
        """Test raising and catching ValidationError."""
        with pytest.raises(ValidationError):
            raise ValidationError("Invalid input")

    def test_raise_fintrack_error(self):
        """Test raising base FinTrackError."""
        with pytest.raises(FinTrackError):
            raise FinTrackError("Generic error")

    def test_exception_message_preserved(self):
        """Test that exception messages are preserved."""
        msg = "Test error message"
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError(msg)
        assert msg in str(exc_info.value)


class TestConfig:
    """Test configuration management."""

    def test_get_data_dir_creates_directory(self):
        """Test that get_data_dir creates the directory."""
        data_dir = Config.get_data_dir("test_user")
        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_get_data_dir_with_default_user(self):
        """Test that get_data_dir works with default user."""
        data_dir = Config.get_data_dir()
        assert data_dir.exists()
        assert "default" in str(data_dir)

    def test_get_db_path_returns_string(self):
        """Test that get_db_path returns a string."""
        db_path = Config.get_db_path("test_user")
        assert isinstance(db_path, str)
        assert db_path.endswith("portfolio.db")

    def test_get_logs_dir_creates_directory(self):
        """Test that get_logs_dir creates the directory."""
        logs_dir = Config.get_logs_dir()
        assert logs_dir.exists()
        assert logs_dir.is_dir()

    def test_get_log_file_returns_string(self):
        """Test that get_log_file returns a string."""
        log_file = Config.get_log_file()
        assert isinstance(log_file, str)
        assert log_file.endswith("fintrack.log")

    def test_multiple_users_separate_directories(self):
        """Test that different users get separate directories."""
        dir1 = Config.get_data_dir("user1")
        dir2 = Config.get_data_dir("user2")
        assert dir1 != dir2
        assert "user1" in str(dir1)
        assert "user2" in str(dir2)

    def test_same_user_same_directory(self):
        """Test that same user gets same directory."""
        dir1 = Config.get_data_dir("same_user")
        dir2 = Config.get_data_dir("same_user")
        assert dir1 == dir2


class TestExceptionMessages:
    """Test error message clarity."""

    def test_validation_error_message_clarity(self):
        """Test that validation error message is clear."""
        msg = "Amount must be positive"
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError(msg)
        assert msg in str(exc_info.value)

    def test_data_fetch_error_includes_context(self):
        """Test that DataFetchError includes context."""
        original_error = ValueError("Network timeout")
        with pytest.raises(DataFetchError) as exc_info:
            raise DataFetchError(f"Failed to fetch: {str(original_error)}") from original_error
        assert "Failed to fetch" in str(exc_info.value)

    def test_database_error_includes_context(self):
        """Test that DatabaseError includes context."""
        with pytest.raises(DatabaseError) as exc_info:
            raise DatabaseError("Database connection failed")
        assert "Database" in str(exc_info.value)
