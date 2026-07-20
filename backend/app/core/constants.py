"""System-wide constants and Enums.

All magic strings live here. Every node label, relationship type, law identifier,
jurisdiction code, and status flag must be defined as an Enum value and referenced
by import — never hardcoded as a string in application code.

Adding a new law:
  1. Add its identifier to LawIdentifier.
  2. Add its jurisdiction to Jurisdiction (if new).
  3. Register it in the LAW_REGISTRY dict at the bottom of this file.
  4. Create a parser under app/ingestion/parsers/<identifier>.py.
  5. Register the parser in app/ingestion/registry.py.
"""

from enum import Enum
from typing import Dict, Any


# ---------------------------------------------------------------------------
# Jurisdiction / Region
# ---------------------------------------------------------------------------


class Jurisdiction(str, Enum):
    """Geographic or supranational jurisdiction codes (ISO 3166-1 / custom)."""

    EU = "EU"
    IN = "IN"          # India
    US = "US"
    UK = "UK"
    AU = "AU"          # Australia
    CA = "CA"          # Canada
    BR = "BR"          # Brazil (LGPD)
    SG = "SG"          # Singapore (PDPA)
    JP = "JP"          # Japan (APPI)
    CN = "CN"          # China (PIPL)
    KR = "KR"          # South Korea (PIPA)
    ZA = "ZA"          # South Africa (POPIA)
    GLOBAL = "GLOBAL"  # Cross-jurisdiction standards / frameworks


# ---------------------------------------------------------------------------
# Law categories
# ---------------------------------------------------------------------------


class LawCategory(str, Enum):
    """Thematic category of a law — used for cross-law correlation queries."""

    DATA_PRIVACY = "DATA_PRIVACY"
    AI_REGULATION = "AI_REGULATION"
    CYBERSECURITY = "CYBERSECURITY"
    FINANCIAL = "FINANCIAL"
    HEALTHCARE = "HEALTHCARE"
    TELECOMMUNICATIONS = "TELECOMMUNICATIONS"
    CONSUMER_PROTECTION = "CONSUMER_PROTECTION"
    SECTOR_SPECIFIC = "SECTOR_SPECIFIC"


# ---------------------------------------------------------------------------
# Law status (ingestion lifecycle)
# ---------------------------------------------------------------------------


class LawStatus(str, Enum):
    """Current ingestion and support lifecycle status of a law."""

    ACTIVE = "active"            # Fully ingested and searchable
    COMING_SOON = "coming_soon"  # Planned but not yet ingested
    DEPRECATED = "deprecated"    # Law replaced or repealed; kept for history
    PARTIAL = "partial"          # Ingested but incomplete (e.g. stubs only)


# ---------------------------------------------------------------------------
# Law identifiers (stable internal keys)
# ---------------------------------------------------------------------------


class LawIdentifier(str, Enum):
    """Stable internal identifiers for each supported law.

    Format: <JURISDICTION>_<SHORTNAME>
    These map 1-to-1 to:
      - The Neo4j node id prefix  (e.g. 'gdpr:art6')
      - The Qdrant collection name (e.g. 'gdpr')
      - The normalized JSON filename (e.g. 'gdpr.json')
      - The parser module name     (e.g. 'eur_lex_gdpr.py')
    """

    # EU
    GDPR = "gdpr"
    AI_ACT = "ai_act"
    NIS2 = "nis2"
    DORA = "dora"

    # India
    DPDP = "dpdp"
    DPDP_RULES = "dpdp_rules"
    IT_ACT = "it_act"
    IT_INTERMEDIARY_RULES_2021 = "it_intermediary_rules_2021"

    # United Kingdom
    UK_GDPR = "uk_gdpr"
    UK_DPA = "uk_dpa"

    # United States
    CCPA = "ccpa"
    HIPAA = "hipaa"

    # Brazil
    LGPD = "lgpd"

    # Singapore
    PDPA_SG = "sg_pdpa"

    # China
    PIPL = "pipl"

    # South Korea
    PIPA_KR = "pipa_kr"

    # South Africa
    POPIA = "popia"

    # Australia
    PRIVACY_ACT_AU = "privacy_act_au"

    # Canada
    PIPEDA = "pipeda"

    # Japan
    APPI = "appi"


# ---------------------------------------------------------------------------
# Neo4j node labels
# ---------------------------------------------------------------------------


class NodeLabel(str, Enum):
    """Neo4j node labels.

    Every MATCH / MERGE / CREATE Cypher clause must use these values —
    never raw strings.
    """

    LAW = "Law"
    CHAPTER = "Chapter"
    ARTICLE = "Article"
    SECTION = "Section"
    RECITAL = "Recital"
    DEFINITION = "Definition"
    CONCEPT = "Concept"
    PENALTY = "Penalty"
    EXCEPTION = "Exception"
    REQUIREMENT = "Requirement"
    COUNTRY = "Country"
    AUTHORITY = "Authority"
    COURT_CASE = "CourtCase"
    GUIDANCE = "Guidance"
    AMENDMENT = "Amendment"


# ---------------------------------------------------------------------------
# Neo4j relationship types
# ---------------------------------------------------------------------------


class RelationshipType(str, Enum):
    """Neo4j relationship types.

    Every relationship in Cypher must use these — no inline strings.
    """

    HAS_CHAPTER = "HAS_CHAPTER"
    HAS_ARTICLE = "HAS_ARTICLE"
    HAS_SECTION = "HAS_SECTION"
    DEFINES = "DEFINES"
    REFERENCES = "REFERENCES"
    HAS_EXCEPTION = "HAS_EXCEPTION"
    HAS_REQUIREMENT = "HAS_REQUIREMENT"
    HAS_CONCEPT = "HAS_CONCEPT"
    INTERPRETS = "INTERPRETS"
    SUPERSEDES = "SUPERSEDES"       # Law B supersedes / amends Law A
    IMPLEMENTS = "IMPLEMENTS"       # national law implements an EU directive
    USES = "USES"                   # Country uses / applies a Law
    AMENDED_BY = "AMENDED_BY"       # Article amended by a later amendment node
    ENFORCED_BY = "ENFORCED_BY"     # Law enforced by an Authority


# ---------------------------------------------------------------------------
# Law registry — single source of truth for all supported laws
# ---------------------------------------------------------------------------
# Each entry carries: identifier, jurisdiction, categories, status, display metadata.
# Parsers and jobs reference this registry instead of scattered hardcoded dicts.


LAW_REGISTRY: Dict[LawIdentifier, Dict[str, Any]] = {
    LawIdentifier.GDPR: {
        "identifier": LawIdentifier.GDPR,
        "name": "GDPR",
        "full_name": "General Data Protection Regulation (EU) 2016/679",
        "jurisdiction": Jurisdiction.EU,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
        "source_type": "html",
        "collection_name": "gdpr",
        "id_prefix": "gdpr",
        "parser_module": "eur_lex_gdpr",
        "description": (
            "Regulation on the protection of natural persons with regard to the "
            "processing of personal data and on the free movement of such data."
        ),
    },
    LawIdentifier.DPDP: {
        "identifier": LawIdentifier.DPDP,
        "name": "DPDP Act",
        "full_name": "Digital Personal Data Protection Act, 2023 (India)",
        "jurisdiction": Jurisdiction.IN,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf",
        "source_type": "pdf",
        "collection_name": "dpdp",
        "id_prefix": "dpdp",
        "parser_module": "india_code_dpdp",
        "description": "An Act to provide for the processing of digital personal data in India.",
    },
    LawIdentifier.DPDP_RULES: {
        "identifier": LawIdentifier.DPDP_RULES,
        "name": "DPDP Rules",
        "full_name": "Digital Personal Data Protection Rules, 2025 (India)",
        "jurisdiction": Jurisdiction.IN,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf",
        "source_type": "pdf",
        "collection_name": "dpdp_rules",
        "id_prefix": "dpdp_rules",
        "parser_module": "india_code_dpdp_rules",
        "description": "Rules notified under the Digital Personal Data Protection Act, 2023, to provide guidelines for notices, consent, data breach reporting, and data protection board functions.",
    },
    LawIdentifier.IT_ACT: {
        "identifier": LawIdentifier.IT_ACT,
        "name": "IT Act",
        "full_name": "Information Technology Act, 2000 (India)",
        "jurisdiction": Jurisdiction.IN,
        "categories": [LawCategory.CYBERSECURITY, LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://www.indiacode.nic.in/bitstream/123456789/1999/1/A2000-21%20%281%29.pdf",
        "source_type": "pdf",
        "collection_name": "it_act",
        "id_prefix": "it_act",
        "parser_module": "india_code_it_act",
        "description": "An Act to provide legal recognition for transactions carried out by means of electronic data interchange and other means of electronic communication, commonly referred to as \"electronic commerce\".",
    },
    LawIdentifier.IT_INTERMEDIARY_RULES_2021: {
        "identifier": LawIdentifier.IT_INTERMEDIARY_RULES_2021,
        "name": "IT Intermediary Rules",
        "full_name": "Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021 (India)",
        "jurisdiction": Jurisdiction.IN,
        "categories": [LawCategory.CYBERSECURITY, LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://www.meity.gov.in/static/uploads/2026/03/0b576f2071694b52e4cd6bb1b6dfab1e.pdf",
        "source_type": "pdf",
        "collection_name": "it_rules_2021",
        "id_prefix": "it_intermediary_rules_2021",
        "parser_module": "india_code_information_act",
        "description": "Rules regulating intermediaries, social media platforms, and digital media ethics under the Information Technology Act, 2000.",
    },
    LawIdentifier.AI_ACT: {
        "identifier": LawIdentifier.AI_ACT,
        "name": "AI Act",
        "full_name": "Artificial Intelligence Act (EU) 2024/1689",
        "jurisdiction": Jurisdiction.EU,
        "categories": [LawCategory.AI_REGULATION],
        "status": LawStatus.COMING_SOON,
        "source_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
        "source_type": "html",
        "collection_name": "ai_act",
        "id_prefix": "aia",
        "parser_module": "eur_lex_ai_act",
        "description": "A harmonized regulatory framework for artificial intelligence across the EU.",
    },
    LawIdentifier.UK_GDPR: {
        "identifier": LawIdentifier.UK_GDPR,
        "name": "UK GDPR",
        "full_name": "UK General Data Protection Regulation",
        "jurisdiction": Jurisdiction.UK,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.COMING_SOON,
        "source_url": "https://www.legislation.gov.uk/eur/2016/679/contents",
        "source_type": "html",
        "collection_name": "uk_gdpr",
        "id_prefix": "ukgdpr",
        "parser_module": "uk_legislation_ukgdpr",
        "description": "The retained EU GDPR as it forms part of UK law post-Brexit.",
    },
    LawIdentifier.CCPA: {
        "identifier": LawIdentifier.CCPA,
        "name": "CCPA",
        "full_name": "California Consumer Privacy Act (US)",
        "jurisdiction": Jurisdiction.US,
        "categories": [LawCategory.DATA_PRIVACY, LawCategory.CONSUMER_PROTECTION],
        "status": LawStatus.COMING_SOON,
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.100.",
        "source_type": "html",
        "collection_name": "ccpa",
        "id_prefix": "ccpa",
        "parser_module": "us_leginfo_ccpa",
        "description": "California state privacy law giving consumers rights over their personal data.",
    },
    LawIdentifier.LGPD: {
        "identifier": LawIdentifier.LGPD,
        "name": "LGPD",
        "full_name": "Lei Geral de Proteção de Dados (Brazil)",
        "jurisdiction": Jurisdiction.BR,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.COMING_SOON,
        "source_url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm",
        "source_type": "html",
        "collection_name": "lgpd",
        "id_prefix": "lgpd",
        "parser_module": "br_planalto_lgpd",
        "description": "Brazilian General Data Protection Law.",
    },
    LawIdentifier.PRIVACY_ACT_AU: {
        "identifier": LawIdentifier.PRIVACY_ACT_AU,
        "name": "Privacy Act",
        "full_name": "Privacy Act 1988 (Australia)",
        "jurisdiction": Jurisdiction.AU,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://www.legislation.gov.au/C2004A03712/latest/text",
        "source_type": "html",
        "collection_name": "privacy_act_au",
        "id_prefix": "privacy_act_au",
        "parser_module": "au_legislation_privacy_act",
        "description": "Australian federal law regulating the handling of personal information.",
    },
    LawIdentifier.PDPA_SG: {
        "identifier": LawIdentifier.PDPA_SG,
        "name": "PDPA",
        "full_name": "Personal Data Protection Act 2012 (Singapore)",
        "jurisdiction": Jurisdiction.SG,
        "categories": [LawCategory.DATA_PRIVACY],
        "status": LawStatus.ACTIVE,
        "source_url": "https://sso.agc.gov.sg/Act/PDPA2012",
        "source_type": "pdf",
        "collection_name": "sg_pdpa",
        "id_prefix": "sg_pdpa",
        "parser_module": "universal_ai",
        "description": "Singapore statutory law governing the collection, use, and disclosure of personal data by organizations.",
    },
}
