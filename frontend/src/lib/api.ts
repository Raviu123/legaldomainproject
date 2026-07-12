import { Law, LegalUnit, GraphData, AskResponse } from './types';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function getLaws(): Promise<Law[]> {
  const res = await fetch(`${BACKEND_URL}/api/v1/documents`);
  if (!res.ok) {
    throw new Error(`Failed to fetch active laws from backend documents list: ${res.statusText}`);
  }
  const activeLaws: string[] = await res.json(); // Returns array of strings e.g. ["GDPR"]
  const activeLawsLower = activeLaws.map((d: string) => d.toLowerCase());

  return [
    {
      id: 'gdpr',
      name: 'GDPR',
      fullName: 'General Data Protection Regulation (EU)',
      description: 'Regulation on the protection of natural persons with regard to the processing of personal data and on the free movement of such data.',
      region: 'European Union',
      status: activeLawsLower.includes('gdpr') ? 'active' : 'coming_soon',
    },
    {
      id: 'dpdp',
      name: 'DPDP Act',
      fullName: 'Digital Personal Data Protection Act, 2023 (India)',
      description: 'An Act to provide for the processing of digital personal data in a manner that recognizes both the right of individuals to protect their personal data and the need to process such personal data for lawful purposes.',
      region: 'India',
      status: activeLawsLower.includes('dpdp') ? 'active' : 'coming_soon',
    },
    {
      id: 'ai_act',
      name: 'AI Act',
      fullName: 'Artificial Intelligence Act (EU)',
      description: 'A harmonized regulatory and legal framework for artificial intelligence across the European Union.',
      region: 'European Union',
      status: activeLawsLower.includes('ai_act') ? 'active' : 'coming_soon',
    },
  ];
}

export async function getLawArticles(lawId: string): Promise<LegalUnit[]> {
  const res = await fetch(`${BACKEND_URL}/api/v1/documents/${lawId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch law ${lawId} articles from backend documents API: ${res.statusText}`);
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
