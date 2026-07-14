"""Ingestion package.

Pipeline stages exposed at the package level for convenience.
The main entrypoint is app/ingestion/run.py.
"""

from app.ingestion.normalizer import load_normalized_file, normalize_and_save
from app.ingestion.registry import get_parser

__all__ = [
    "get_parser",
    "normalize_and_save",
    "load_normalized_file",
]
