# Legal Knowledge Graph RAG System (MVP)

A hybrid Graph + Vector RAG system designed to answer complex legal questions by combining semantic search (Qdrant vector store) with relational context (Neo4j knowledge graph).

## Project Structure

```text
legal-graph-rag/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app entrypoint
│   │   ├── api/                   # Router definitions (ask, graph, health)
│   │   ├── core/                  # Configuration, logging, constants
│   │   ├── ingestion/             # Crawler, parsing, normalization
│   │   └── models/                # Pydantic schemas (LegalUnit)
│   └── tests/                     # Unit & integration tests
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router and pages
│   │   ├── components/            # Sidebar, Header, LawViewer, GraphExplorer
│   │   └── lib/                   # API client and TypeScript definitions
│   └── public/
│       └── data/                  # Static law files (GDPR)
└── data/
    └── normalized/                # Ingested and normalized law JSONs
```

## How to Run Locally

### 1. Run the Backend

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your `.env` configuration (see `.env.example`).
5. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   The backend API will be available at [http://localhost:8000](http://localhost:8000).

### 2. Run the Frontend

1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install the node packages:
   ```bash
   npm install
   ```
3. Run the Next.js development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at [http://localhost:3000](http://localhost:3000).

## Tech Stack

- **Backend**: FastAPI, Pydantic, Uvicorn
- **Graph Database**: Neo4j (Cypher query layer)
- **Vector Database**: Qdrant
- **LLM Orchestration**: LangGraph
- **Frontend**: Next.js (App Router, React 19, TypeScript), Tailwind CSS, Lucide Icons
