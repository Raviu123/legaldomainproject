import { Law, LegalUnit, GraphData, AskResponse } from './types';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function getLaws(): Promise<Law[]> {
  const res = await fetch(`${BACKEND_URL}/api/v1/laws`);
  if (!res.ok) {
    throw new Error(`Failed to fetch laws from backend: ${res.statusText}`);
  }
  const laws: any[] = await res.json();

  const regionMapping: Record<string, string> = {
    EU: "European Union",
    IN: "India",
    AU: "Australia",
    UK: "United Kingdom",
    US: "United States",
    BR: "Brazil",
    SG: "Singapore",
    JP: "Japan",
  };

  return laws.map((law: any) => ({
    id: law.id,
    name: law.name,
    fullName: law.full_name,
    description: law.description,
    region: regionMapping[law.jurisdiction] || law.jurisdiction,
    status: law.status === "active" ? "active" : "coming_soon",
  }));
}

export async function getLawArticles(lawId: string): Promise<LegalUnit[]> {
  const res = await fetch(`${BACKEND_URL}/api/v1/documents/${lawId}`);
  if (!res.ok) {
    const error = new Error(`Failed to fetch law ${lawId} articles from backend documents API: ${res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export async function getGraphData(): Promise<GraphData> {
  const res = await fetch(`${BACKEND_URL}/api/v1/graph`);
  if (!res.ok) {
    throw new Error(`Failed to fetch graph data from backend: ${res.statusText}`);
  }
  return await res.json();
}

export async function askQuestion(question: string, law?: string, topK?: number): Promise<AskResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v1/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, law, top_k: topK }),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch RAG response from backend: ${res.statusText}`);
  }
  return await res.json();
}
