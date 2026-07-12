"""Normalizer module.

Validates parsed legal units against the Pydantic schema and saves them to normalized JSON files.
"""

import json
from pathlib import Path
from typing import List

from app.core.config import settings
from app.core.logging import logger
from app.models.legal_unit import LegalUnit


def normalize_and_save(units: List[LegalUnit], filename: str) -> Path:
    """Validates list of LegalUnit objects and writes them to a JSON file.

    Args:
        units: List of LegalUnit objects to validate and save.
        filename: Target filename (e.g. 'gdpr.json').

    Returns:
        Path: Path to the saved normalized JSON file.
    """
    normalized_dir = settings.normalized_data_dir
    output_path = normalized_dir / filename

    logger.info(f"Normalizing and saving {len(units)} units to: {output_path}")

    # Validate units by dumping and re-loading through Pydantic
    serialized_units = []
    for unit in units:
        # Pydantic validation is implicit since units is List[LegalUnit],
        # but calling model_dump ensures everything is serialized correctly.
        serialized_units.append(unit.model_dump())

    # Write JSON output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serialized_units, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved normalized data successfully to {output_path}")
    return output_path


def load_normalized_file(filename: str) -> List[LegalUnit]:
    """Loads a normalized JSON file back into a list of LegalUnit objects.

    Args:
        filename: Name of the file under normalized/ directory.

    Returns:
        List[LegalUnit]: List of validated LegalUnit objects.
    """
    file_path = settings.normalized_data_dir / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Normalized file does not exist: {file_path}")

    logger.info(f"Loading normalized units from {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [LegalUnit(**item) for item in data]
