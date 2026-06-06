import logging
import sys
import os
from typing import Dict, Any

# Try to import structlog, handle if not installed
try:
    import structlog
    from structlog.types import Processor
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

def setup_logging(config: Dict[str, Any]):
    """
    Configures logging for the application, using structlog for structured JSON logging.
    If structlog is not installed, it falls back to a basic standard logging configuration.
    """
    log_level_str = config.get("logging", {}).get("level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    if not STRUCTLOG_AVAILABLE:
        print("WARNING: structlog not found. Falling back to basic logging. "
              "For structured JSON logs, please run 'pip install structlog'.", file=sys.stderr)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return

    # --- Structlog Configuration ---

    # Define processors for structlog. These are functions that process log records.
    shared_processors: List[Processor] = [
        structlog.contextvars.merge_contextvars, # Allows binding context (e.g., request_id)
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Configure the standard logging module to be a sink for structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout, # Log to stdout
        level=log_level,
    )

    # Configure structlog itself
    structlog.configure(
        processors=shared_processors + [
            # This processor must be last to do the final rendering.
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Add file logging if enabled in config
    if config.get("logging", {}).get("log_to_file", False):
        log_path = config.get("logging", {}).get("log_path", "logs/stratum.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            file_handler = logging.FileHandler(log_path)

            # Create a separate formatter for the file to ensure it also gets JSON
            # The JSONRenderer will be part of the structlog processors chain
            # The standard library handler just needs to pass the message through.
            # We can use a simple formatter for this.
            file_handler.setFormatter(logging.Formatter("%(message)s"))

            # Get the root logger and add the handler
            # Note: We add it to the root logger so all logs (including from dependencies)
            # that go through standard logging are captured.
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)

            logger = structlog.get_logger("logging_setup")
            logger.info("File logging enabled.", path=log_path)
        except Exception as e:
            logger = structlog.get_logger("logging_setup")
            logger.error("Failed to set up file logging.", path=log_path, error=str(e), exc_info=True)

    logger = structlog.get_logger("logging_setup")
    logger.info("Structured logging configured.", log_level=log_level_str)
