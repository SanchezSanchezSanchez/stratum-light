#!/usr/bin/env python3
# Tier-aware Logging Configuration Module for STRATUM_LIGHT

import os
import sys
import logging
import logging.handlers
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

# Import environment tiers
try:
    from config.environment import EnvironmentTier
except ImportError:
    # Define fallback if environment module is not available
    from enum import Enum
    class EnvironmentTier(Enum):
        DEVELOPMENT = "development"
        STAGING = "staging"
        PRODUCTION = "production"

# Define log formats
DEFAULT_FORMAT = '%(asctime)s|%(levelname)s|%(name)s|%(message)s'
DETAILED_FORMAT = '%(asctime)s|%(levelname)s|%(name)s|%(filename)s:%(lineno)d|%(message)s'
JSON_FORMAT = '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","file":"%(filename)s","line":%(lineno)d,"message":"%(message)s"}'

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def __init__(self, fmt=None, datefmt=None, style='%', include_stack_info=False):
        """Initialize JSON formatter"""
        super().__init__(fmt, datefmt, style)
        self.include_stack_info = include_stack_info
    
    def format(self, record):
        """Format log record as JSON"""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "file": record.filename,
            "line": record.lineno,
            "message": record.getMessage()
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add stack info if requested
        if self.include_stack_info and record.stack_info:
            log_data["stack_info"] = record.stack_info
        
        # Add any extra attributes
        for key, value in record.__dict__.items():
            if key not in ["args", "asctime", "created", "exc_info", "exc_text", "filename",
                          "funcName", "id", "levelname", "levelno", "lineno", "module",
                          "msecs", "message", "msg", "name", "pathname", "process",
                          "processName", "relativeCreated", "stack_info", "thread", "threadName"]:
                log_data[key] = value
        
        return json.dumps(log_data)

class SensitiveFilter(logging.Filter):
    """Filter to redact sensitive information in logs"""
    
    def __init__(self, sensitive_keys=None):
        """Initialize filter with sensitive keys to redact"""
        super().__init__()
        self.sensitive_keys = sensitive_keys or [
            "key", "secret", "password", "token", "credential", "auth", 
            "license", "api_key", "private", "cert"
        ]
    
    def filter(self, record):
        """Filter log record to redact sensitive information"""
        if isinstance(record.msg, str):
            msg = record.msg
            for key in self.sensitive_keys:
                # Look for patterns like key=value or "key": "value"
                for pattern in [f"{key}=", f'"{key}":', f"'{key}':"]:
                    if pattern in msg.lower():
                        # Find the value after the pattern and redact it
                        start = msg.lower().find(pattern) + len(pattern)
                        # Skip whitespace
                        while start < len(msg) and msg[start].isspace():
                            start += 1
                        
                        if start < len(msg):
                            if msg[start] in ['"', "'"]:
                                # Find the closing quote
                                quote = msg[start]
                                end = msg.find(quote, start + 1)
                                if end > start:
                                    msg = msg[:start] + quote + "[REDACTED]" + quote + msg[end+1:]
                            else:
                                # Find the end of the value (whitespace or comma)
                                end = start
                                while end < len(msg) and msg[end] not in [' ', ',', '\n', '\t', ';']:
                                    end += 1
                                msg = msg[:start] + "[REDACTED]" + msg[end:]
            
            record.msg = msg
        
        return True

def configure_logging(env_context: Dict[str, Any]) -> None:
    """
    Configure logging based on environment context
    
    Args:
        env_context: Environment context from environment schema
    """
    # Get environment tier
    tier = env_context.get('tier', EnvironmentTier.DEVELOPMENT)
    
    # Get logging configuration
    log_level = env_context.get('log_level', 'INFO').upper()
    log_to_file = env_context.get('logging', {}).get('log_to_file', False)
    log_path = env_context.get('logging', {}).get('log_path', 'logs/stratum.log')
    
    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Apply tier-specific logging configuration
    if tier == EnvironmentTier.DEVELOPMENT:
        _configure_development_logging(log_to_file, log_path)
    elif tier == EnvironmentTier.STAGING:
        _configure_staging_logging(log_to_file, log_path)
    elif tier == EnvironmentTier.PRODUCTION:
        _configure_production_logging(log_to_file, log_path)
    else:
        # Fallback to development logging
        _configure_development_logging(log_to_file, log_path)
    
    # Add sensitive information filter to all handlers
    sensitive_filter = SensitiveFilter()
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)
    
    # Log configuration complete
    logging.info(f"Logging configured for {tier.value} environment at {log_level} level")
    if log_to_file:
        logging.info(f"Logging to file: {log_path}")

def _configure_development_logging(log_to_file: bool, log_path: str) -> None:
    """
    Configure logging for development environment
    
    Args:
        log_to_file: Whether to log to file
        log_path: Path to log file
    """
    # Configure console handler with detailed format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
    logging.getLogger().addHandler(console_handler)
    
    # Add file handler if requested
    if log_to_file:
        _add_file_handler(log_path, DETAILED_FORMAT)
    
    # Set verbose logging for development
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Reduce logging level for some verbose libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def _configure_staging_logging(log_to_file: bool, log_path: str) -> None:
    """
    Configure logging for staging environment
    
    Args:
        log_to_file: Whether to log to file
        log_path: Path to log file
    """
    # Configure console handler with default format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    logging.getLogger().addHandler(console_handler)
    
    # Add file handler with JSON format
    if log_to_file:
        _add_file_handler(log_path, format_string=None, json_format=True)
    
    # Set default logging level for staging
    logging.getLogger().setLevel(logging.INFO)

def _configure_production_logging(log_to_file: bool, log_path: str) -> None:
    """
    Configure logging for production environment
    
    Args:
        log_to_file: Whether to log to file
        log_path: Path to log file
    """
    # Configure console handler with minimal format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    console_handler.setLevel(logging.WARNING)  # Only warnings and above to console
    logging.getLogger().addHandler(console_handler)
    
    # Add file handler with JSON format (always in production)
    _add_file_handler(log_path, format_string=None, json_format=True, max_bytes=10485760, backup_count=10)
    
    # Set default logging level for production
    logging.getLogger().setLevel(logging.INFO)
    
    # Reduce logging level for some libraries
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('requests').setLevel(logging.ERROR)

def _add_file_handler(
    log_path: str, 
    format_string: Optional[str] = DEFAULT_FORMAT, 
    json_format: bool = False,
    max_bytes: int = 5242880,  # 5MB
    backup_count: int = 5
) -> None:
    """
    Add file handler to root logger
    
    Args:
        log_path: Path to log file
        format_string: Log format string
        json_format: Whether to use JSON format
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
    """
    # Create log directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    
    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, 
        maxBytes=max_bytes, 
        backupCount=backup_count
    )
    
    # Set formatter
    if json_format:
        file_handler.setFormatter(JsonFormatter())
    else:
        file_handler.setFormatter(logging.Formatter(format_string))
    
    # Add handler to root logger
    logging.getLogger().addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Get logger with the given name
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

# Example usage
if __name__ == "__main__":
    # Example environment context
    example_env = {
        "tier": EnvironmentTier.DEVELOPMENT,
        "log_level": "DEBUG",
        "logging": {
            "log_to_file": True,
            "log_path": "logs/test.log"
        }
    }
    
    # Configure logging
    configure_logging(example_env)
    
    # Test logging
    logger = get_logger("test")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Test sensitive information redaction
    logger.info("API key=secret123 should be redacted")
    logger.info('{"password": "secret123"} should be redacted')
    
    # Test exception logging
    try:
        1 / 0
    except Exception as e:
        logger.exception("This is an exception message")
