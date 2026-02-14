"""Custom exceptions for FinTrack."""


class FinTrackError(Exception):
    """Base exception for all FinTrack errors."""

    pass


class ValidationError(FinTrackError):
    """Raised when input validation fails."""

    pass


class DataFetchError(FinTrackError):
    """Raised when data fetching from Yahoo Finance fails."""

    pass


class PriceError(FinTrackError):
    """Raised when price data is unavailable or invalid."""

    pass


class DatabaseError(FinTrackError):
    """Raised for database-related errors."""

    pass


class ConfigError(FinTrackError):
    """Raised for configuration errors."""

    pass
