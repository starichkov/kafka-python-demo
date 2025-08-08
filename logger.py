"""
Logging Configuration Module

This module provides a centralized logging configuration utility for the Kafka Python demo project.
It creates standardized loggers with consistent formatting and configurable log levels via environment
variables. The loggers output to stdout with timestamps and are designed to work well in both
development and production environments.

The LOG_LEVEL environment variable can be set to control the logging level (DEBUG, INFO, WARNING, ERROR).
If not specified, it defaults to INFO level.

Example:
    >>> from logger import get_logger
    >>> logger = get_logger('my_component')
    >>> logger.info('This is an info message')
    2025-08-08 22:53:00 [INFO] my_component: This is an info message
"""

import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Create and configure a logger with standardized formatting and output.

    This function creates a logger with a specific name and configures it with:
    - StreamHandler outputting to stdout
    - Consistent timestamp and level formatting
    - Configurable log level via LOG_LEVEL environment variable
    - Prevention of duplicate handlers on subsequent calls

    Args:
        name (str): The name for the logger, typically the module or component name.
                   This name will appear in the log output format.

    Returns:
        logging.Logger: A configured logger instance ready for use.

    Example:
        >>> logger = get_logger('producer')
        >>> logger.info('Message sent successfully')
        2025-08-08 22:53:00 [INFO] producer: Message sent successfully
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))
        logger.propagate = False

    return logger
