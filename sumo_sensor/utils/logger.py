"""
Logging utilities for SUMO sensor simulator.
Handles file and stream logging with proper formatting.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = 'sumo_sensor',
    log_file: Optional[str] = 'logs/sensor.log',
    level: int = logging.INFO,
    console_output: bool = True
) -> logging.Logger:
    """
    Setup logger with file and optional console output.

    Args:
        name: Logger name
        log_file: Path to log file (None to disable file logging)
        level: Logging level
        console_output: Whether to output to console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter: ISO timestamp | level | message
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str = 'sumo_sensor') -> logging.Logger:
    """Get existing logger instance"""
    return logging.getLogger(name)


class SensorLogger:
    """
    Specialized logger for sensor operations.
    Adds junction_id context to log messages.
    """

    def __init__(self, junction_id: str, base_logger: Optional[logging.Logger] = None):
        self.junction_id = junction_id
        self.logger = base_logger or get_logger()

    def _format_message(self, message: str) -> str:
        """Add junction context to message"""
        return f"[Junction {self.junction_id}] {message}"

    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(self._format_message(message))

    def info(self, message: str):
        """Log info message"""
        self.logger.info(self._format_message(message))

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(self._format_message(message))

    def error(self, message: str, exc_info: bool = False):
        """Log error message"""
        self.logger.error(self._format_message(message), exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False):
        """Log critical message"""
        self.logger.critical(self._format_message(message), exc_info=exc_info)

    def exception(self, message: str):
        """Log exception with traceback"""
        self.logger.exception(self._format_message(message))
