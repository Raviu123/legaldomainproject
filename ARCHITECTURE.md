# Architecture Guide — Legal Knowledge Graph RAG

> **This document is the canonical reference for how this system is built.**
> Every engineer and AI agent working on this codebase must read and follow it.
> It supersedes any conflicting documentation in other files.

---

## 1. Purpose & Design Goals

This system answers complex legal questions across **50+ global regulatory laws** using a hybrid **Knowledge Graph + Vector Search** retrieval-augmented generation (RAG) approach. Plain vector-only RAG is deliberately not used because legal texts are:

- **Relational** — articles reference other articles, definitions, exceptions
- **Hierarchical** — Laws → Chapters → Articles → Sections → Sub-clauses
- **Cross-jurisdictional** — GDPR (EU), DPDP (India), CCPA (USA) overlap and cross-reference
- **Amendment-sensitive** — Laws get updated; the system must detect and re-ingest changes

Design goals, in priority order:

1. **Correctness** — Every answer must be traceable to specific legal articles. Hallucination is a bug.
2. **Scalability** — Adding a new law (parser + registry entry) must require < 1 hour of work.
3. **Maintainability** — A new engineer can understand the full system from this document alone.
4. **Freshness** — Laws must be monitored for amendments and re-ingested automatically.

---

## 2. High-Level Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Official Legal Sources       │
                    │  (EUR-Lex, India Code, legislation.  │
                    │   gov.uk, leginfo, planalto.gov.br…) │
                    └────────────────┬────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   Ingestion Pipeline  │
                          │  (CLI + Admin API)    │
                          └──────────┬───────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐
    │  Crawler        │   │  Parser Registry│   │  Enrichment      │
    │  (HTTP cache)   │──▶│  (per-law)      │──▶│  Structure +     │
    │                 │   │                 │   │  Entity Extract  │
    └─────────────────┘   └─────────────────┘   └──────┬───────────┘
                                                        │
                                         ┌──────────────┼────────────────┐
                                         ▼              ▼                ▼
                                ┌─────────────┐  ┌───────────┐  ┌──────────────┐
                                │   Neo4j     │  │  Qdrant   │  │  Normalized  │
                                │  (Graph DB) │  │  (Vector) │  │   JSON files │
                                └──────┬──────┘  └─────┬─────┘  └──────────────┘
                                       │               │
                          ┌────────────┼───────────────┘
                          ▼            ▼
                    ┌─────────────────────────┐
                    │     Hybrid Retrieval     │
                    │  Graph + Vector + Keyword│
                    │     + Merge & Rank       │
                    └────────────┬────────────┘
                                 │
                          ┌──────▼──────┐
                          │  LLM Layer  │
                          │ (Orchestrat)│
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │  FastAPI    │
                          │  REST API   │
                          └─────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │       Frontend           │
                    │  (Next.js — Q&A + Graph) │
                    └─────────────────────────┘
```

---

## 3. Repository Layout

```
legaldata_graphRag/
├── ARCHITECTURE.md           ← YOU ARE HERE — canonical system guide
├── BACKEND_GUIDE.md          ← Deep-dive implementation reference
├── AGENTS.md                 ← Rules for AI coding agents
├── context.md                ← Product context and goals
├── conventions.md            ← Code style and formatting rules
│
├── backend/                  ← FastAPI backend
│   ├── .env.example          ← Configuration template (copy to .env)
│   ├── docker-compose.yml    ← Neo4j + Qdrant local services
│   ├── requirements.txt      ← Python dependencies
│   ├── pyproject.toml        ← Black / isort / ruff / pytest config
│   │
│   └── app/
│       ├── main.py                    ← FastAPI app, router registration, lifecycle
│       │
│       ├── core/                      ← Foundation — everything else imports from here
│       │   ├── config.py              ← All settings from env vars (Pydantic Settings)
│       │   ├── constants.py           ← Enums: LawIdentifier, NodeLabel, RelationshipType,
│       │   │                          │   Jurisdiction, LawCategory, LawStatus, LAW_REGISTRY
│       │   └── logging.py             ← Logger instances (logger, neo4j_logger, qdrant_logger)
│       │
│       ├── models/                    ← Pydantic domain models (shared by all layers)
│       │   └── legal_unit.py          ← LegalUnit + DefinitionModel — the universal data contract
│       │
│       ├── ingestion/                 ← Data pipeline (fetch → parse → enrich → persist)
│       │   ├── run.py                 ← CLI entrypoint — generic for ALL laws
│       │   ├── registry.py            ← Maps LawIdentifier → Parser class
│       │   ├── normalizer.py          ← Save/load normalized JSON files
│       │   ├── crawler/
│       │   │   └── crawler.py         ← HTTP fetcher with caching + rate limiting
│       │   └── parsers/
│       │       ├── base.py            ← BaseLegalParser abstract class (parse() contract)
│       │       ├── eur_lex_gdpr.py    ← GDPR HTML parser (EUR-Lex)  ← ACTIVE
│       │       ├── eur_lex_ai_act.py  ← AI Act HTML parser           ← stub (to implement)
│       │       ├── india_code_dpdp.py ← DPDP PDF parser              ← stub (to implement)
│       │       └── ...                ← One file per source × law combination
│       │
│       ├── extraction/                ← Enrichment stages (run after parsing)
│       │   ├── structure_extractor.py ← Regex: cross-references + definitions
│       │   └── entity_extractor.py    ← Hybrid regex + LLM: semantic concepts
│       │
│       ├── graph/                     ← Neo4j client and schema operations
│       │   ├── client.py              ← Singleton Neo4jClient with constraint setup
│       │   └── schema.py              ← Cypher loaders (two-pass) + integrity checks
│       │
│       ├── vector/                    ← Qdrant client, embedding model, batch upsert
│       │   ├── client.py              ← Singleton QdrantClientManager
│       │   ├── embeddings.py          ← Local SentenceTransformer wrapper
│       │   └── schema.py              ← load_legal_units_to_vector_db() + batch logic
│       │
│       ├── retrieval/                 ← Three independently-testable retrieval legs + merger
│       │   ├── vector_search.py       ← Qdrant ANN search (BGE embeddings)
│       │   ├── graph_search.py        ← Neo4j APOC path traversal from anchor IDs
│       │   ├── keyword_search.py      ← Neo4j scored keyword scan
│       │   └── merger.py             ← Deduplicate + weight + rank top-K
│       │
│       ├── llm/                       ← LLM orchestration
│       │   ├── orchestrator.py        ← Format context → call LLM → validate JSON → retry
│       │   └── prompts/               ← Versioned prompt templates (never inline strings)
│       │       └── ask_v1.txt         ← Current production prompt
│       │
│       ├── jobs/                      ← Scheduled / background maintenance jobs
│       │   └── check_updates.py       ← HTTP ETag-based law change detector
│       │
│       └── api/                       ← FastAPI routers (one file per resource group)
│           ├── health.py              ← GET /health, GET /health/llm
│           ├── ask.py                 ← POST /ask (main RAG endpoint)
│           ├── graph.py               ← GET /graph (visualization data)
│           ├── documents.py           ← GET /documents, GET /documents/{law}
│           ├── laws.py                ← GET /laws, GET /laws/{law_id} (registry-driven)
│           └── admin.py               ← POST /admin/ingest, POST /admin/check-updates
│
├── data/                             ← All data artifacts (gitignored except schema)
│   ├── raw/                          ← Untouched source downloads (html, pdf, xml)
│   ├── normalized/                   ← Processed JSON (one file per law: gdpr.json, etc.)
│   ├── cache/                        ← Concept extraction cache, HTTP ETag cache
│   └── graph_exports/                ← Optional Cypher export snapshots
│
├── frontend/                         ← Next.js app (TypeScript)
│   └── (see frontend conventions in conventions.md)
│
└── tests/                            ← Mirrors backend/app/ structure
    ├── ingestion/
    │   ├── test_crawler.py
    │   ├── test_parsers/
    │   │   └── test_eur_lex_gdpr.py
    │   └── test_normalizer.py
    ├── extraction/
    │   ├── test_structure_extractor.py
    │   └── test_entity_extractor.py
    ├── retrieval/
    │   ├── test_vector_search.py
    │   ├── test_graph_search.py
    │   ├── test_keyword_search.py
    │   └── test_merger.py
    └── api/
        ├── test_ask.py
        ├── test_graph.py
        └── test_health.py
```

---

## 4. The Law Registry — Single Source of Truth

`app/core/constants.py :: LAW_REGISTRY` is the **single source of truth** for every law in the system. It drives:

| Consumer | How it uses LAW_REGISTRY |
|---|---|
| `api/laws.py` | Builds the `/api/v1/laws` catalog response |
| `api/admin.py` | Validates `/admin/ingest` requests |
| `ingestion/run.py` | Looks up `source_url`, `source_type`, `collection_name` |
| `jobs/check_updates.py` | Iterates ACTIVE laws for update checks |
| `retrieval/vector_search.py` | Maps law name → Qdrant collection |

**Adding a new law requires exactly these steps (no other files need editing):**

```
Step 1: Add to constants.py
  a. Add law identifier to LawIdentifier enum
  b. Add jurisdiction to Jurisdiction enum (if new)
  c. Add entry to LAW_REGISTRY dict

Step 2: Create parser
  a. Create app/ingestion/parsers/<source>_<law>.py
  b. Subclass BaseLegalParser, implement parse()

Step 3: Register parser
  a. Import class in app/ingestion/registry.py
  b. Add to PARSER_REGISTRY dict

Step 4: Run pipeline
  python -m app.ingestion.run --law <law_id>
```

---

## 5. Data Flow & Layer Contracts

### 5.1 The `LegalUnit` contract

`app/models/legal_unit.py :: LegalUnit` is the single data model that crosses all layer boundaries:

```
Crawl → Parse → [LegalUnit] → Enrich → [LegalUnit+] → Neo4j + Qdrant
                                                              ↓
                                            Retrieval → [LegalUnit dict] → LLM
```

**Never** create a law-specific data model. If a source has unusual fields, add optional fields to `LegalUnit` with a clear docstring explaining the use case.

### 5.2 ID convention

Every legal unit gets a stable string ID: `<law_prefix>:<type><number>`

| ID | Meaning |
|---|---|
| `gdpr:art6` | GDPR Article 6 |
| `gdpr:recital14` | GDPR Recital 14 |
| `gdpr:def_personal_data` | GDPR definition of "personal data" |
| `dpdp:sec16` | DPDP Act Section 16 |
| `aia:art6` | AI Act Article 6 |

This ID is used as:
- The Neo4j `id` property on every node
- The seed for the deterministic Qdrant point UUID (`uuid.uuid5(NAMESPACE_DNS, unit_id)`)
- The join key between graph and vector layers

**Never change an ID format for an existing law** without a migration plan — it would break all cross-references.

---

## 6. Knowledge Graph Schema

### Node types

| Label | Key property | Description |
|---|---|---|
| `Law` | `name` (unique) | The law itself (e.g. "GDPR") |
| `Chapter` | `id` (unique) | Structural grouping (e.g. "gdpr:chap_ii") |
| `Article` | `id` (unique) | An article (e.g. "gdpr:art6") |
| `Recital` | `id` (unique) | A preamble recital |
| `Definition` | `id` (unique) | A defined term |
| `Concept` | `name` (unique) | A shared semantic theme |
| `Authority` | `name` (unique) | Regulatory body (e.g. "EDPB") |
| `Amendment` | `id` (unique) | A subsequent amendment to an article |

### Relationship types

| Relationship | From → To | Meaning |
|---|---|---|
| `HAS_CHAPTER` | Law → Chapter | Law contains chapter |
| `HAS_ARTICLE` | Chapter → Article/Recital | Chapter contains article |
| `DEFINES` | Article → Definition | Article defines a term |
| `REFERENCES` | Article → Article | Article cites another article |
| `HAS_CONCEPT` | Article/Recital → Concept | Article relates to concept |
| `HAS_EXCEPTION` | Article → Article | Article has an exception in another |
| `SUPERSEDES` | Law → Law | Law B replaces Law A |
| `IMPLEMENTS` | Law → Law | National law implements EU directive |
| `AMENDED_BY` | Article → Amendment | Article was amended |
| `ENFORCED_BY` | Law → Authority | Law is enforced by a regulator |

---

## 7. Retrieval Architecture

The retrieval pipeline runs **three independent legs** in parallel, then merges:

```
Query
  │
  ├─── [1] Vector Search  ──── Qdrant (cosine ANN, BGE-small)     weight=1.0
  │           │
  │    vector_hit_ids + explicit article mentions from query
  │           │
  ├─── [2] Graph Traversal ─── Neo4j (APOC subgraph, 2 hops)      weight=0.8
  │                            via REFERENCES, DEFINES, HAS_CONCEPT
  │
  └─── [3] Keyword Search ──── Neo4j (scored CONTAINS, top-6)     weight=0.5
                               title=×2, term=×3, text=×1

Merger: dedup by ID, max-weighted score, accumulate retrieval_sources → top-12
```

**Each leg must be independently callable and independently testable.**
The merger must be a pure function — deterministic, loggable, no LLM calls.

### Score ranges by source

| Source | Raw score range | Weight | Effective range |
|---|---|---|---|
| Vector | 0.0 – 1.0 (cosine) | 1.0 | 0.0 – 1.0 |
| Graph | 0.75 (fixed) | 0.8 | 0.60 |
| Keyword | 0.0 – 0.6 (normalised) | 0.5 | 0.0 – 0.30 |

---

## 8. LLM Layer Design

The orchestrator is intentionally thin:

1. **Format context** — structured string from retrieval results (article + title + url + text)
2. **Load prompt** — from versioned `.txt` file in `llm/prompts/`
3. **Call LLM** — via OpenAI-compatible API
4. **Validate output** — against `LlmAnswer` Pydantic model
5. **Retry once** — if JSON validation fails, append corrective instruction and retry
6. **Raise** — if second attempt also fails (never silently return garbage)

**Prompt versioning:**  
All prompts live in `app/llm/prompts/` as `.txt` files named `<purpose>_v<N>.txt`.  
Never inline prompt strings in Python code.  
When changing a prompt, create `ask_v2.txt` and update the path constant in orchestrator.py — keep `ask_v1.txt` for rollback.

---

## 9. Ingestion Job System

### CLI (manual / CI)

```bash
# Full pipeline
python -m app.ingestion.run --law gdpr

# Refresh only vector store (data already in Neo4j)
python -m app.ingestion.run --law gdpr --skip-fetch --skip-graph --force-recreate-vector

# Dry run (parse + enrich only, no DB writes)
python -m app.ingestion.run --law gdpr --dry-run
```

### API (admin)

```http
POST /api/v1/admin/ingest
X-Admin-Key: <ADMIN_API_KEY>
Content-Type: application/json

{"law": "gdpr", "skip_fetch": false}
```

### Scheduled update checks

The `jobs/check_updates.py` job uses HTTP conditional GET (ETag / Last-Modified) to detect source document changes without re-downloading. It stores version metadata in `data/cache/law_versions.json`.

**Recommended schedule:** Daily at 03:00 UTC via cron or APScheduler.

```bash
# Manual trigger
curl -X POST http://localhost:8000/api/v1/admin/check-updates?auto_reingest=true \
  -H "X-Admin-Key: your-key"
```

---

## 10. Adding a New Law — Checklist

Use this checklist every time a new law is added:

- [ ] Add `LawIdentifier` enum value to `app/core/constants.py`
- [ ] Add `Jurisdiction` entry if jurisdiction is new
- [ ] Add full entry to `LAW_REGISTRY` (name, url, source_type, collection_name, id_prefix, parser_module, categories, status=`COMING_SOON`)
- [ ] Create `app/ingestion/parsers/<source>_<law>.py` subclassing `BaseLegalParser`
- [ ] Write unit test with a real sample fixture: `tests/ingestion/test_parsers/test_<law>.py`
- [ ] Register parser in `app/ingestion/registry.py :: PARSER_REGISTRY`
- [ ] Set law status to `ACTIVE` in `LAW_REGISTRY` after first successful ingestion run
- [ ] Run: `python -m app.ingestion.run --law <law_id> --dry-run` to validate parsing
- [ ] Run: `python -m app.ingestion.run --law <law_id>` for full ingestion
- [ ] Verify graph: open Neo4j Browser and run `MATCH (n:Law {name: '<NAME>'}) RETURN n`
- [ ] Update `BACKEND_GUIDE.md` and `README.md` to include the new law

---

## 11. Coding Standards (Summary)

Full rules are in `conventions.md`. Key points:

| Rule | Detail |
|---|---|
| No magic strings | Use `LawIdentifier`, `NodeLabel`, `RelationshipType` enums everywhere |
| No hardcoded law lists | Read from `LAW_REGISTRY` |
| No print() | Use `logger` from `app.core.logging` |
| Type hints everywhere | All function signatures: params + return type |
| Pydantic for all boundaries | API in/out, LLM output, ingestion output |
| Prompts in files | `llm/prompts/<name>_v<N>.txt` — never inline |
| Tests mirror app/ | `tests/ingestion/`, `tests/retrieval/`, `tests/api/` |
| MERGE not CREATE | All Neo4j writes use MERGE for idempotency |
| Stable IDs | Qdrant UUID = `uuid5(NAMESPACE_DNS, unit.id)` — never random |

---

## 12. Environment Setup

```bash
# 1. Start databases
cd backend
docker-compose up -d

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run ingestion (GDPR first — cleanest source)
python -m app.ingestion.run --law gdpr

# 6. Start the API server
uvicorn app.main:app --reload --port 8000

# 7. Explore
open http://localhost:8000/docs        # Swagger UI
open http://localhost:7474             # Neo4j Browser
```

---

## 13. What NOT to Do

These are intentional architecture constraints, not suggestions:

- ❌ **Don't create per-law schemas** — `LegalUnit` is the contract for all laws
- ❌ **Don't add per-law if/elif in run.py** — use the registry/parser dispatch pattern
- ❌ **Don't put prompts inline in Python** — they go in `llm/prompts/`
- ❌ **Don't use `CREATE` in Neo4j** — always `MERGE` for idempotency
- ❌ **Don't couple retrieval legs** — graph/vector/keyword must be independently callable
- ❌ **Don't return uncited LLM answers** — a citation-less answer is a bug
- ❌ **Don't skip the graph** — vector-only RAG defeats the purpose of this system
- ❌ **Don't ingest laws outside the registry** — register them first, then ingest
- ❌ **Don't hardcode Qdrant collection names** — read from `LAW_REGISTRY["collection_name"]`
- ❌ **Don't silence exceptions during ingestion** — fail loudly with context
