"""Ingestion parser registry.

This is the single place that maps a LawIdentifier to its concrete parser class.
To add a new law:
  1. Create app/ingestion/parsers/<parser_module>.py implementing BaseLegalParser.
  2. Import it here and add it to the PARSER_REGISTRY dict.
  3. Register the law's metadata in app/core/constants.py :: LAW_REGISTRY.

The run_pipeline() function in run.py calls get_parser() to dynamically
dispatch to the correct parser without any per-law if/elif branching.
"""

from typing import Dict, Type

from app.core.constants import LawIdentifier
from app.ingestion.parsers.base import BaseLegalParser
from app.ingestion.parsers.eur_lex_gdpr import EurLexGdprParser
from app.ingestion.parsers.india_code_dpdp import IndiaCodeDpdpParser
from app.ingestion.parsers.au_privacy_act import AustraliaPrivacyActParser
from app.ingestion.parsers.india_code_it_act import IndiaCodeItActParser
from app.ingestion.parsers.india_code_dpdp_rules import IndiaCodeDpdpRulesParser
from app.ingestion.parsers.india_code_information_act import ItIntermediaryRules2021Parser
from app.ingestion.parsers.universal_ai import UniversalAiParser


# ---------------------------------------------------------------------------
# Registry: LawIdentifier -> Parser class
# ---------------------------------------------------------------------------

PARSER_REGISTRY: Dict[LawIdentifier, Type[BaseLegalParser]] = {
    LawIdentifier.GDPR: EurLexGdprParser,
    LawIdentifier.DPDP: IndiaCodeDpdpParser,
    LawIdentifier.PRIVACY_ACT_AU: AustraliaPrivacyActParser,
    LawIdentifier.IT_ACT: IndiaCodeItActParser,
    LawIdentifier.DPDP_RULES: IndiaCodeDpdpRulesParser,
    LawIdentifier.IT_INTERMEDIARY_RULES_2021: ItIntermediaryRules2021Parser,
}


def get_parser(law: LawIdentifier) -> BaseLegalParser:
    """Returns an instantiated parser for the given law.

    If no hardcoded parser is registered for the law, defaults to the UniversalAiParser
    providing 100% format and law compatibility out of the box.
    """
    parser_cls = PARSER_REGISTRY.get(law)
    if parser_cls is None:
        return UniversalAiParser()
    return parser_cls()

