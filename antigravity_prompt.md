You are building a Legal Knowledge Graph RAG system. Before writing any code, read the following three files in this order and treat them as binding instructions for the entire project:

1. `docs/context.md` — what we're building, the MVP scope, the full 8-step pipeline, the architecture, and the tech stack. This defines WHAT to build.
2. `docs/conventions.md` — coding standards, project structure, naming, schema, testing, and git conventions. This defines HOW the code must be written.
3. `docs/agents.md` — working process: build order, what to verify at each step, what not to do. This defines HOW YOU should work.

Do not skip reading any of these. Do not start writing application code until you've read all three.

## Your task

Scaffold and build this project incrementally, following the exact build order in `docs/agents.md` §1:

1. Scaffold the repo structure exactly as specified in `docs/conventions.md` §1 (backend FastAPI skeleton, config, logging, docker-compose for Neo4j + Qdrant, `.env.example`).
2. Set up the Python environment. I already have `requirements.txt` — use it as-is, don't add or remove packages without telling me why.
3. Build the ingestion pipeline for **GDPR only** first: crawler → parser (EUR-Lex HTML) → normalizer → JSON output conforming to the shared `LegalUnit` Pydantic schema described in `context.md` Step 2.
4. Build the legal structure extractor for GDPR (chapters, articles, definitions, cross-references).
5. Build the Neo4j knowledge graph loader using the schema in `context.md` Step 3–4 (node types, relationships, concepts). Use idempotent `MERGE`, not `CREATE`.
6. Generate embeddings for the GDPR data and load them into Qdrant, using the same node `id` as the join key between graph and vector store.
7. Once GDPR is fully working end-to-end and I've confirmed it, repeat ingestion for the DPDP Act, then the AI Act, reusing the same schema and pipeline — don't build a parallel one.
8. Build hybrid retrieval: graph search (Cypher), vector search (Qdrant), keyword search (BM25) — as independently callable functions — then a merger that combines and ranks results.
9. Build the LLM answer generation layer (LangGraph orchestration + versioned prompt templates) that takes merged context and returns a structured answer: `answer`, `sources`, `confidence`, `related_laws`. The LLM must only cite from provided context and must say "not found in the provided sources" if it can't answer — no hallucinated citations.
10. Wire it all into a `/api/v1/ask` FastAPI endpoint.
11. Build a minimal Next.js frontend: first a simple Q&A interface hitting `/api/v1/ask`, then the interactive graph explorer described in `context.md` Step 8.

## Ground rules while you work

- Work in small increments. After each step above, show me something runnable and real (actual parsed JSON, actual Cypher query results, actual API response) — not code that "should work."
- Never fabricate or stub legal text/data to make something look complete.
- Ask me before swapping any part of the tech stack (FastAPI, Neo4j, Qdrant, LangGraph, Next.js, Claude/OpenAI for embeddings).
- Follow `docs/conventions.md` for every file you write — formatting, naming, typing, schema, error handling, logging, testing.
- Don't jump ahead to LLM answer generation before graph + vector retrieval both actually work — the whole point of this project is hybrid retrieval, not plain vector RAG.
- All installation of Python packages, Neo4j, Qdrant, Node, etc. will be handled by me — just tell me what's needed and reference `requirements.txt`; don't try to install system-level things yourself unless asked.

Start with Step 1 (repo scaffold) and Step 2 (GDPR ingestion), then stop and show me the output before continuing to the graph loader.
