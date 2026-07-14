"""Base parser interface.

Every source-specific parser MUST subclass BaseLegalParser and implement parse().
This contract guarantees that all parsers produce the same LegalUnit shape,
regardless of source format (HTML, PDF, XML, JSON).

Implementing a new parser:
    1. Create app/ingestion/parsers/<jurisdiction>_<lawname>.py
    2. Subclass BaseLegalParser
    3. Implement parse(file_path, url, law) -> List[LegalUnit]
    4. Register in app/ingestion/registry.py
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from app.core.constants import LawIdentifier
from app.models.legal_unit import LegalUnit


class BaseLegalParser(ABC):
    """Abstract base class for all law-specific parsers.

    Parsers are stateless — they receive a cached file path and return
    a list of LegalUnit objects. They must not write to disk or call
    external services.
    """

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse a raw downloaded file into normalized LegalUnit objects.

        Args:
            file_path: Path to the locally cached source file.
            url: The original source URL (stored on every LegalUnit for citation).
            law: The LawIdentifier enum value for the law being parsed.

        Returns:
            List of LegalUnit objects ready for enrichment and loading.

        Raises:
            ValueError: If the file cannot be parsed (malformed structure).
            FileNotFoundError: If file_path does not exist.
        """
        ...

    def source_label(self) -> str:
        """Human-readable label for the source provider.

        Override in subclasses to return e.g. 'eur-lex', 'india-code', 'uk-legislation'.
        Defaults to the class name.
        """
        return self.__class__.__name__
