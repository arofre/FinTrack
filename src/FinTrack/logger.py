"""Logging configuration for FinTrack."""
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import Config


def setup_logger(
    name: str, level: int = logging.INFO, log_to_file: bool = True
) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    Args:
        name: Logger name (usually __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to also log to file

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Portfolio initialized")
    """
    logger = logging.getLogger(name)

    # Don't add handlers if logger already has them
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if enabled)
    if log_to_file:
        try:
            log_file = Config.get_log_file()
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create one if it doesn't exist.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        setup_logger(name)
    return logger
