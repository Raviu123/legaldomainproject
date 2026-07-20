export interface Definition {
  term: string;
  definition: string;
}

export interface LegalUnit {
  id: string;
  law: string;
  chapter: string;
  article?: string;
  section?: string;
  title?: string;
  text: string;
  source: string;
  url: string;
  definitions?: Definition[];
  concepts?: string[];
  references?: string[];
}

export interface Law {
  id: string;
  name: string;
  fullName: string;
  description: string;
  region: string;
  status: 'active' | 'coming_soon';
}

export interface GraphNode {
  id: string;
  label: string;
  properties: {
    name?: string;
    title?: string;
    text?: string;
    [key: string]: any;
  };
}

export interface GraphRelationship {
  source: string;
  target: string;
  type: string;
  properties?: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphRelationship[];
}

export interface AskSource {
  id: string;
  url: string;
  law: string;
}

export interface AskResponse {
  answer: string;
  sources: AskSource[];
  confidence: number;
  related_laws: string[];
}

export interface RegistryEntry {
  identifier: string;
  name: string;
  full_name: string;
  jurisdiction: string;
  status: string;
  source_url: string;
}

export interface IngestOptions {
  law: string;
  skip_fetch?: boolean;
  skip_graph?: boolean;
  skip_vector?: boolean;
  force_recreate_vector?: boolean;
  dry_run?: boolean;
}

export interface IngestResponse {
  status: string;
  law: string;
  message: string;
}

