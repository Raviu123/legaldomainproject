# Conventions

These conventions apply to all code in this project. They exist to keep the codebase clean, consistent, and maintainable as more laws/agents/modules get added later. Follow them strictly unless a file-specific comment says otherwise.

## 1. Project structure

```
legal-graph-rag/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app entrypoint
│   │   ├── api/                   # route definitions (one file per resource)
│   │   │   ├── ask.py
│   │   │   ├── graph.py
│   │   │   └── health.py
│   │   ├── core/                  # config, settings, logging, constants
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── ingestion/              # crawler, parser, normalizer
│   │   │   ├── crawler/
│   │   │   ├── parsers/            # one parser per source (eur_lex.py, india_code.py)
│   │   │   └── normalizer.py
│   │   ├── extraction/             # legal structure + entity + relationship extraction
│   │   │   ├── structure_extractor.py
│   │   │   ├── entity_extractor.py
│   │   │   └── relationship_extractor.py
│   │   ├── graph/                  # Neo4j client, schema, cypher queries
│   │   │   ├── client.py
│   │   │   ├── schema.py
│   │   │   └── queries/
│   │   ├── vectorstore/            # Qdrant client, embeddings
│   │   │   ├── client.py
│   │   │   └── embeddings.py
│   │   ├── retrieval/              # hybrid retrieval logic
│   │   │   ├── graph_search.py
│   │   │   ├── vector_search.py
│   │   │   ├── keyword_search.py
│   │   │   └── merger.py
│   │   ├── llm/                    # prompt templates, LangGraph orchestration
│   │   │   ├── prompts/
│   │   │   └── orchestrator.py
│   │   └── models/                 # Pydantic schemas (request/response, domain models)
│   ├── tests/                      # mirrors app/ structure
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   └── (Next.js app — standard structure, see frontend conventions below)
├── data/
│   ├── raw/                        # untouched source downloads, gitignored
│   ├── normalized/                 # normalized JSON per law
│   └── graph_exports/
├── docs/
│   ├── context.md
│   ├── conventions.md
│   └── agents.md
└── README.md
```

## 2. Python conventions

- **Python version**: 3.11+
- **Formatting**: `black` (line length 100), `isort` for imports. Run both before every commit.
- **Linting**: `ruff`. No unused imports, no unused variables, no bare `except:`.
- **Type hints**: mandatory on all function signatures (params + return type). Use `pydantic` models for any structured data crossing a boundary (API, ingestion output, LLM output).
- **Docstrings**: every public function/class gets a one-line docstring minimum. Use Google-style docstrings for anything non-trivial.
- **Naming**:
  - `snake_case` for functions/variables/modules
  - `PascalCase` for classes and Pydantic models
  - `UPPER_SNAKE_CASE` for constants
  - Files named after what they contain, not generic names (`eur_lex_parser.py`, not `parser2.py`)
- **No magic strings**: law names, node labels, relationship types live in `core/constants.py` as an Enum, not hardcoded strings scattered across files.
- **Config**: all config (DB URIs, API keys, model names) comes from environment variables via a single `core/config.py` using `pydantic-settings`. Never hardcode secrets or endpoints.
- **Logging**: use the `logging` module via `core/logging.py`. No `print()` statements in application code. Log at appropriate levels (`debug` for pipeline internals, `info` for pipeline stage completion, `warning`/`error` for recoverable/unrecoverable issues).
- **Error handling**: fail loudly during ingestion (a malformed article should raise, not silently skip) — log with enough context to identify which law/article/source failed. Never swallow exceptions silently.

## 3. Data schema conventions

- Every ingested legal unit must conform to one shared Pydantic model (`models/legal_unit.py`) regardless of source jurisdiction. Fields: `law`, `chapter`, `article`, `section`, `title`, `text`, `source`, `url`, plus optional `definitions`, `concepts`, `references`.
- Node/relationship names in Neo4j must exactly match the Enum values in `core/constants.py` — no ad hoc labels invented inline in Cypher queries.
- Every graph node representing a legal unit must carry a stable `id` (e.g. `gdpr:art6`, `dpdp:sec16`) so graph and vector store can be joined by ID.
- Qdrant point IDs must equal the corresponding Neo4j node `id` — this is the join key between graph and vector layers. Never let them drift.

## 4. API conventions

- REST via FastAPI. Versioned routes: `/api/v1/...`.
- Every endpoint has a Pydantic request model and response model — no raw `dict` in/out.
- Every answer-generating endpoint must return: `answer`, `sources` (list of article/section IDs + URLs), `confidence`, `related_laws`. Never return an answer without sources.
- Use dependency injection for DB clients (Neo4j driver, Qdrant client) — don't instantiate clients inside route handlers.

## 5. LLM / prompt conventions

- All prompts live in `llm/prompts/` as versioned template files (not inlined as Python strings in business logic).
- Every prompt that asks the LLM to produce structured output must specify: "respond only in JSON, no preamble, no markdown fences" — and the caller must validate the response against a Pydantic model before using it.
- Prompts must explicitly instruct the LLM to cite only from the provided context and to say "not found in the provided sources" rather than hallucinate an answer.

## 6. Git conventions

- Branch naming: `feature/<short-name>`, `fix/<short-name>`, `chore/<short-name>`.
- Commit messages: Conventional Commits format — `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`.
- No committing raw downloaded legal documents or `.env` files — add to `.gitignore`.
- Every PR that touches ingestion or graph schema must include a short note on what changed in the schema (since it affects both Neo4j and Qdrant).

## 7. Testing conventions

- `pytest` for all backend tests, mirroring `app/` folder structure under `tests/`.
- Every parser (EUR-Lex, India Code) needs a unit test with a small fixture sample of real source HTML/PDF — not just mocked data.
- Every Cypher query used in retrieval needs an integration test against a small seeded test graph.
- Hybrid retrieval merger logic needs unit tests with fabricated graph/vector/keyword result sets to confirm merge/ranking behavior is deterministic.

## 8. Frontend conventions (Next.js)

- TypeScript only, no `.js` files.
- Component naming: `PascalCase` for components, colocate styles.
- Fetch data via typed API client functions in `lib/api/`, never inline `fetch()` calls in components.
- Graph visualization component must be isolated and reusable (`components/GraphExplorer.tsx`) — it should accept graph data as props, not fetch internally.

## 9. Documentation conventions

- Every new module gets a short header comment explaining its role in the pipeline (which step from `context.md` it implements).
- `README.md` at the repo root must always have an up-to-date "how to run this locally" section.
- Any deviation from `context.md`'s architecture must be documented with a reason, in a `docs/decisions.md` (ADR-style, create if needed).
