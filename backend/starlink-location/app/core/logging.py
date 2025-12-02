"""Structured logging configuration."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Log levels
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log line
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class StructuredLogger(logging.Logger):
    """Extended logger with structured logging support."""

    def _log_with_extras(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info: Optional[Any] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Internal method to log with extra fields.

        Args:
            level: Log level
            msg: Log message
            args: Message format arguments
            exc_info: Exception info
            extra_fields: Additional JSON fields
        """
        if self.isEnabledFor(level):
            record = self.makeRecord(
                self.name, level, "(unknown file)", 0, msg, args, exc_info, **kwargs
            )

            if extra_fields:
                record.extra_fields = extra_fields

            self.handle(record)

    def debug_json(
        self, message: str, extra_fields: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log debug message with optional extra fields."""
        self._log_with_extras(logging.DEBUG, message, (), extra_fields=extra_fields)

    def info_json(
        self, message: str, extra_fields: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log info message with optional extra fields."""
        self._log_with_extras(logging.INFO, message, (), extra_fields=extra_fields)

    def warning_json(
        self, message: str, extra_fields: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log warning message with optional extra fields."""
        self._log_with_extras(logging.WARNING, message, (), extra_fields=extra_fields)

    def error_json(
        self,
        message: str,
        extra_fields: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log error message with optional extra fields."""
        self._log_with_extras(
            logging.ERROR, message, (), exc_info=exc_info, extra_fields=extra_fields
        )

    def critical_json(
        self,
        message: str,
        extra_fields: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log critical message with optional extra fields."""
        self._log_with_extras(
            logging.CRITICAL, message, (), exc_info=exc_info, extra_fields=extra_fields
        )


def setup_logging(
    level: str = LOG_LEVEL_INFO,
    json_format: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure structured logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format if True, standard format otherwise
        log_file: Optional log file path
    """
    # Set custom logger class
    logging.setLoggerClass(StructuredLogger)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Create file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        StructuredLogger instance
    """
    return logging.getLogger(name)
