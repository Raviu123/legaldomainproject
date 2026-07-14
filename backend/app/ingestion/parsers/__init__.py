"""Ingestion parsers package.

One module per source + law combination. All parsers subclass BaseLegalParser
and are registered in app/ingestion/registry.py.

Naming convention:
  <source_provider>_<law_identifier>.py

  Examples:
    eur_lex_gdpr.py          — EUR-Lex HTML → GDPR
    eur_lex_ai_act.py        — EUR-Lex HTML → AI Act
    india_code_dpdp.py       — India Code PDF → DPDP Act
    uk_legislation_ukgdpr.py — legislation.gov.uk HTML → UK GDPR
    us_leginfo_ccpa.py       — leginfo.legislature.ca.gov → CCPA

Each parser lives here; its class is imported only in registry.py.
"""
