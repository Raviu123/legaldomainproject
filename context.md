Context: Legal Knowledge Graph RAG System (MVP)

1. What we're building

A system that answers legal questions like:


"Can personal data be transferred outside India?"



...not with keyword search, but by:


Finding relevant laws
Finding relevant sections/articles
Finding related definitions
Finding exceptions
Finding regulator guidance
Generating an answer with citations


This is a hybrid Graph + Vector RAG system over legal text. Plain RAG (chunk + embed + retrieve) is not enough because law is structured and relational — articles reference other articles, define terms, have exceptions, and get interpreted by guidance/case law. A knowledge graph captures that structure; a vector store captures semantic similarity; together they give much stronger retrieval than either alone.

2. Scope for MVP — pick ONE domain

Do not ingest "all the world's laws." Scope is intentionally narrow:


GDPR (EU)
DPDP Act (India — Digital Personal Data Protection Act)
AI Act (EU)


That's it. Three laws is enough to prove the concept end-to-end (parsing → graph → vector → hybrid retrieval → cited answer → interactive graph UI).

Official sources to parse from (exact documents, not just domains):

LawOfficial documentIdentifierFormatGDPRRegulation (EU) 2016/679CELEX 32016R0679HTML/XMLAI ActRegulation (EU) 2024/1689CELEX 32024R1689HTML/XMLDPDP ActDigital Personal Data Protection Act, 2023 (Act No. 22 of 2023)—PDF

Exact URLs to crawl:


GDPR — https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng (consolidated version: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679)
AI Act — https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng
DPDP Act — https://www.indiacode.nic.in/bitstream/123456789/22037/1/a2023-22.pdf (India Code official PDF)

Optional companion source: DPDP Rules, 2025 (notified 14 Nov 2025) at https://www.dpdpa.com/DPDP_Rules_2025_English_only.pdf — not required for MVP but useful later since the Act and Rules are meant to be read together.





Notes for the crawler/parser:


EUR-Lex pages have an HTML "TXT" view and a PDF view for the same CELEX ID — prefer HTML for GDPR/AI Act since it's far easier to split into articles cleanly than PDF.
The DPDP Act only exists as a PDF from India Code — pdfplumber will need to handle section/sub-section numbering carefully since the PDF has gazette headers/footers and line-numbered clauses.
Always store the exact source URL and a fetch timestamp with every ingested unit (already part of the LegalUnit schema) — laws get amended, and there's no ingestion history without this.


(Later, out of MVP scope: UK Legislation, US Code, more Indian acts, court cases from IndianKanoon/CURIA.)

3. High-level architecture

                Official Sources
        (India Code, EUR-Lex, DPDP, GDPR, AI Act)
                       │
                       ▼
               Ingestion Pipeline
                       │
                       ▼
             Document Parser
        (PDF / HTML / XML / JSON / Text)
                       │
                       ▼
          Legal Structure Extractor
                       │
                       ▼
           Knowledge Graph Builder
                       │
                       ▼
                    Neo4j
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
    Vector Store               Graph Search
     (Qdrant)                   (Cypher)
          │                         │
          └────────────┬────────────┘
                        ▼
                Hybrid Retrieval
                        │
                        ▼
                       LLM
                        │
                        ▼
             AI Answer + Sources

4. Step-by-step plan

Step 1 — Pick the domain

Locked: GDPR + DPDP Act + AI Act. Nothing else in MVP.

Step 2 — Parse the documents into legal units

Don't store one giant document per law. Split into structured units:

GDPR
 └─ Chapter I
     └─ Article 1
     └─ Article 2
     └─ Article 3
     ...
 └─ Article 83
 └─ Recitals
 └─ Definitions
 └─ Cross references

Each unit becomes its own JSON object, e.g.:

json{
  "law": "GDPR",
  "chapter": "Chapter II",
  "article": "Article 6",
  "title": "Lawfulness of Processing",
  "text": "Processing shall be lawful only if...",
  "source": "eur-lex",
  "url": "..."
}

Do the same normalization for DPDP Act and AI Act (chapter/section/article naming will differ slightly per jurisdiction — normalize into a common schema, see Step 3).

Step 3 — Build the Legal Knowledge Graph

Go beyond chunk+embed. Model law as a graph.

Node labels:
(:Law) (:Chapter) (:Article) (:Section) (:Definition) (:Concept) (:Penalty) (:Exception) (:Requirement) (:Country) (:Authority) (:CourtCase) (:Guidance)

Relationships:

Law        -[:HAS_CHAPTER]->     Chapter
Chapter    -[:HAS_ARTICLE]->     Article
Article    -[:HAS_SECTION]->     Section
Article    -[:DEFINES]->         Definition
Article    -[:REFERENCES]->      Article
Article    -[:HAS_EXCEPTION]->   Exception
Article    -[:HAS_REQUIREMENT]-> Requirement
Guidance   -[:INTERPRETS]->      Article
CourtCase  -[:INTERPRETS]->      Article
Country    -[:USES]->            Law

Step 4 — Add semantic entities (concepts)

Extract domain concepts per article (e.g., Article 6 of GDPR → Consent, Personal Data, Processing, Controller, Lawful Basis, Legitimate Interest) and add them as graph nodes:

Article 6 -[:HAS_CONCEPT]-> Consent
Article 6 -[:HAS_CONCEPT]-> Controller
Article 6 -[:HAS_CONCEPT]-> Legitimate Interest

This turns the graph from "document structure" into a real semantic network.

Step 5 — Create embeddings

For every Article, Section, Definition, Guidance unit → generate an embedding and store it in Qdrant, with metadata:

json{
  "law": "GDPR",
  "article": "6",
  "chapter": "II",
  "country": "EU",
  "url": "...",
  "type": "article"
}

Step 6 — Hybrid retrieval

Given a query (e.g., "Can biometric data be transferred outside India?"):


Graph search: Biometric Data → Personal Data → DPDP Act → Section 16 → REFERENCES → Cross-border transfer
Vector search: semantically similar chunks across all three laws
Keyword search: exact term matches (BM25)
Merge all three result sets into one ranked context set


Step 7 — Generate the AI answer

Feed merged context into the LLM:

User Question
   ↓
Graph Context
   ↓
Vector Context
   ↓
Relevant Definitions
   ↓
Related Sections
   ↓
Prompt
   ↓
LLM
   ↓
Answer + Sources + Relevant Articles + Confidence + Related Laws

The answer must always cite the specific article/section it came from — no uncited claims.

Step 8 — Interactive graph (the "wow" feature)

Let the user visually click through relationships instead of reading raw PDFs, e.g.:

GDPR → Article 6 → Consent → Processing → Special Categories
     → Article 9 → Biometric Data → Article 32 → Security

This is the differentiator from a plain chatbot — it's explorable, not just a text answer.

5. Recommended tech stack

ComponentTechnologyBackendFastAPILLM OrchestrationLangGraphLLMClaude (primary), GPT-4.1/GPT-5, or Gemini as alternatesKnowledge GraphNeo4jVector DBQdrantEmbeddingsOpenAI text-embedding-3-large or BAAI/bge-m3ParserUnstructured + BeautifulSoup + pdfplumberEntity ExtractionLLM + spaCy / GLiNERRetrievalHybrid (Graph + Vector + BM25)FrontendNext.js

6. Ingestion pipeline flow

Official Source
     ↓
Crawler
     ↓
Raw HTML/PDF/XML
     ↓
Parser
     ↓
Document Normalizer
     ↓
Legal Structure Extractor
     ↓
Entity Extractor
     ↓
Relationship Extractor
     ↓
Knowledge Graph Loader
     ↓
Embedding Generator
     ↓
Vector Store

7. Ingestion trigger & execution model

Ingestion is manually triggered, per-law, batch execution — not a background job, not scheduled, not automatic.

Trigger: a CLI command, e.g.:

bashpython -m app.ingestion.run --law gdpr
python -m app.ingestion.run --law dpdp
python -m app.ingestion.run --law ai_act

Within one law, the pipeline stages run strictly in sequence (crawl → parse → normalize → extract structure → extract entities/relationships → load graph → embed → load vector store), and each stage's output should be inspectable before moving to the next.

Across laws, ingestion is done one law at a time for the MVP — GDPR first (cleanest HTML source, used to validate the pipeline), then DPDP Act, then AI Act — reusing the same pipeline code and schema rather than building a parallel path per law. Do not ingest all three simultaneously before GDPR has been verified end-to-end.

Re-runs are expected and safe: since it's manually triggered, the same law will be re-ingested multiple times during development. Neo4j loads use MERGE (not CREATE) and Qdrant point IDs are stable and derived from the graph node ID, so re-running --law gdpr refreshes data instead of duplicating it.

Out of MVP scope, but natural next steps: a --law all flag to batch all three, a scheduled job to re-check sources for amendments, or an admin API endpoint (POST /api/v1/ingest) to trigger ingestion remotely instead of via CLI only.

8. Definition of "done" for the MVP


 GDPR, DPDP Act, and AI Act fully ingested and normalized into the common JSON schema
 Knowledge graph populated in Neo4j with all node types and relationships from Step 3–4
 Embeddings for every article/section/definition stored in Qdrant with metadata
 Hybrid retrieval (graph + vector + keyword) working and merging results
 /ask API endpoint that takes a question and returns an answer with citations, relevant articles, confidence, and related laws
 A minimal interactive graph view in the frontend where a user can click through relationships
 Can correctly answer the example question: "Can personal data be transferred outside India?" with citations to the actual DPDP Act section