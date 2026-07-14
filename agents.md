# Agents.md — Instructions for AI Coding Agents

This file is for any AI agent (Antigravity CLI, Claude Code, Cursor agent, etc.) working autonomously or semi-autonomously on this repository.

> **Primary reference: Read `ARCHITECTURE.md` first and fully before touching any code.**
> It is the canonical system guide and supersedes all other documentation for structural decisions.
> Then read `context.md` (product goals) and `conventions.md` (code style) before writing code.
> This file governs *how* you work — not *what* to build (`context.md`) or *how to format code* (`conventions.md`).



## 1. Order of operations

Build in this order. Do not skip ahead — later stages depend on earlier ones being real and tested, not stubbed.

1. **Scaffold the repo** per the structure in `conventions.md` §1. Set up FastAPI skeleton, config, logging, `requirements.txt`, `.env.example`, Neo4j + Qdrant docker-compose for local dev.
2. **Ingestion for ONE law first** (recommend starting with GDPR since EUR-Lex HTML is cleaner than DPDP PDF). Get raw fetch → parse → normalize → JSON working end-to-end for GDPR before touching DPDP or AI Act.
3. **Legal structure extractor** for that one law — chapters/articles/definitions correctly split.
4. **Knowledge graph loader** — push GDPR into Neo4j with the schema from `context.md` §3. Verify with manual Cypher queries that the graph looks right before automating more.
5. **Embeddings + Qdrant** for the same GDPR data.
6. **Repeat ingestion (steps 2–5) for DPDP Act, then AI Act**, reusing the same normalizer/schema — do not create a parallel schema per law.
7. **Hybrid retrieval** — implement graph search, vector search, keyword search separately, each independently testable, then the merger.
8. **LLM answer generation** — prompt template + orchestration via LangGraph, returning answer + sources + confidence + related laws.
9. **API layer** — wire retrieval + LLM into `/api/v1/ask`.
10. **Frontend** — basic Q&A UI first, then the interactive graph explorer last.

Do not jump to Step 8 (LLM answers) before Steps 1–7 are real. A demo that "answers questions" using only vector search with no graph is not what this project is — it defeats the purpose.

## 2. Working style

- **Work in small, verifiable increments.** After each numbered step above, there should be something you can actually run and inspect (a script that prints parsed JSON, a Cypher query that returns real nodes, an API call that returns a real answer) — not just code that "should work."
- **Never fabricate data.** If a source page fails to parse, log the failure and stop — don't silently generate placeholder articles or synthetic legal text to make the pipeline "look" complete.
- **Ask before making architectural changes.** If you think Neo4j, Qdrant, or the recommended stack in `context.md` should be swapped for something else, say so explicitly and explain why — don't silently substitute (e.g. don't swap Qdrant for Pinecone, or Neo4j for a plain SQL table, without flagging it).
- **Respect the schema.** The Pydantic `LegalUnit` model and the graph node/relationship types are the contract between ingestion, graph, and vector layers. If you need to extend the schema, update it in one place and propagate — don't create a law-specific one-off schema.
- **Cite-or-refuse.** Any LLM-generated answer without traceable sources back to specific articles/sections is a bug, not a feature to "improve later."

## 3. When implementing parsers

- Each source (EUR-Lex, India Code) gets its own parser module under `ingestion/parsers/`, but all parsers must output the same normalized `LegalUnit` shape.
- Handle the real messiness of legal documents: nested sub-clauses, cross-references like "as defined in Article 4(1)", footnotes, amendments. Don't assume every article is flat text.
- Rate-limit and cache raw downloads under `data/raw/` so repeated ingestion runs don't hammer the source sites.

## 4. When implementing the graph

- Load into Neo4j using idempotent `MERGE` (not `CREATE`) so re-running ingestion doesn't duplicate nodes.
- After loading each law, run a small validation script that checks: every `Article` has a `law`, every `DEFINES`/`REFERENCES` edge points to a node that actually exists (no dangling references), no orphan nodes.

## 5. When implementing retrieval

- Graph search, vector search, and keyword search must be independently callable and independently testable — don't couple them into one function.
- The merger should be a clear, inspectable ranking/dedup function, not an opaque LLM call — log which sources came from which retrieval method so behavior is debuggable.

## 6. When implementing the LLM layer

- Keep prompts in versioned files, not inline strings (see `conventions.md` §5).
- Always pass retrieved context with explicit source labels (law, article, URL) so the LLM can cite precisely.
- Validate LLM JSON output against a Pydantic model before returning it from the API — if validation fails, retry once with a corrective instruction, then fail loudly rather than returning malformed data.

## 7. Definition of done for any task

A task is done when:
- Code follows `conventions.md`
- It's actually runnable (not just written) and you've verified the output
- Tests exist for the new logic (or a clear reason is stated for why not, e.g. "pending real source data")
- No hardcoded secrets, no stubbed/fake data pretending to be real ingestion output

## 8. What NOT to do

- Don't build a plain vector-only RAG "shortcut" and call it done — the graph is core to this project, not optional.
- Don't ingest laws outside the MVP scope (GDPR, DPDP Act, AI Act) unless explicitly asked.
- Don't skip the interactive graph frontend — it's called out in `context.md` as the key differentiator.
- Don't silently change the tech stack (FastAPI/Neo4j/Qdrant/LangGraph/Next.js) — flag any proposed substitution first.
