"""Application logging configuration.

Sets up standardized loggers for console output and file logging under a new logs folder.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Define the logs directory in the project root
base_dir = Path(__file__).resolve().parent.parent.parent
logs_dir = base_dir / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

# Standard logging format
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(log_format)


def setup_logger(
    name: str,
    log_file: str,
    level: Optional[int] = None,
    console_level: Optional[int] = None,
) -> logging.Logger:
    """Sets up a logger with a file handler and optional console handler.

    Args:
        name: The name of the logger.
        log_file: Name of the log file under the logs/ directory.
        level: Logging level (e.g. logging.INFO).
        console_level: If set, adds a console handler with this specific level.
                       If None, no console handler is added.

    Returns:
        logging.Logger: The configured logger.
    """
    if level is None:
        level = logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to prevent duplicate messages
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_path = logs_dir / log_file
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    if console_level is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Disable propagation to the root logger to avoid duplicate log entries
    logger.propagate = False

    return logger


# Initialize and expose default loggers
# general logger: logs INFO level to app.log and stdout console
logger = setup_logger("legal_graph_rag", "app.log", console_level=logging.INFO)

# neo4j logger: logs INFO level to neo4j_ingestion.log, but only WARNING/ERROR to console to prevent flooding
neo4j_logger = setup_logger("neo4j_ingestion", "neo4j_ingestion.log", console_level=logging.WARNING)

# qdrant logger: logs INFO level to qdrant_ingestion.log, but only WARNING/ERROR to console to prevent flooding
qdrant_logger = setup_logger("qdrant_ingestion", "qdrant_ingestion.log", console_level=logging.WARNING)
