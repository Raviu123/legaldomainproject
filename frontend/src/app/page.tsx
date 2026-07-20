'use client';

import React, { useState, useEffect } from 'react';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import LawViewer from '../components/LawViewer';
import GraphExplorer from '../components/GraphExplorer';
import AddLawTab from '../components/AddLawTab';
import { Law, LegalUnit, GraphData } from '../lib/types';
import { getLaws, getLawArticles, getGraphData } from '../lib/api';
import { BookOpen, Network, PlusCircle, ShieldCheck, ShieldAlert } from 'lucide-react';

export default function Home() {
  // Navigation & configuration state
  const [activeTab, setActiveTab] = useState<'laws' | 'graph' | 'add_law'>('laws');
  const [selectedLawId, setSelectedLawId] = useState<string>('');
  
  // Data state
  const [laws, setLaws] = useState<Law[]>([]);
  const [articles, setArticles] = useState<LegalUnit[]>([]);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  
  const [activeArticleId, setActiveArticleId] = useState<string>('');

  // Loading & error state
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lawNotIngested, setLawNotIngested] = useState<boolean>(false);

  // Backend connection status state
  const [backendConnected, setBackendConnected] = useState<boolean>(false);

  // Stats computed from loaded data
  const stats = {
    nodes: graphData.nodes.length,
    edges: graphData.edges.length,
    vectors: articles.filter(a => a.article || a.chapter !== 'Recitals').length,
  };

  // 1. Check API health & connectivity
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const res = await fetch(`${backendUrl}/api/v1/health`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'healthy') {
            setBackendConnected(true);
            return;
          }
        }
        setBackendConnected(false);
      } catch (err) {
        setBackendConnected(false);
      }
    };

    checkBackendHealth();
    // Re-check health every 15 seconds
    const interval = setInterval(checkBackendHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // 2. Fetch laws catalog
  useEffect(() => {
    const loadLaws = async () => {
      try {
        setError(null);
        setLoading(true);
        const data = await getLaws();
        setLaws(data);
        if (data.length > 0 && !selectedLawId) {
          setSelectedLawId(data[0].id);
        }
      } catch (err: any) {
        console.error('Error loading laws from backend:', err);
        setError(`Failed to connect to backend: ${err.message || 'Unknown error'}`);
      } finally {
        setLoading(false);
      }
    };
    loadLaws();
  }, [selectedLawId]);

  // 3. Fetch articles and graph data for the selected law
  useEffect(() => {
    const loadLawContent = async () => {
      if (!selectedLawId) return;
      
      try {
        setError(null);
        setLawNotIngested(false);
        setLoading(true);
        
        // Fetch articles
        const articleData = await getLawArticles(selectedLawId);
        setArticles(articleData);
        
        // Select the first article by default when changing laws
        if (articleData.length > 0) {
          setActiveArticleId(articleData[0].id);
        } else {
          setActiveArticleId('');
        }

        // Fetch graph structural data
        try {
          const gData = await getGraphData(selectedLawId);
          setGraphData(gData);
        } catch (graphErr) {
          console.warn("Failed to load graph data, setting empty graph:", graphErr);
          setGraphData({ nodes: [], edges: [] });
        }
      } catch (err: any) {
        console.error('Error loading law content from backend:', err);
        if (err.status === 404) {
          setArticles([]);
          setLawNotIngested(true);
        } else {
          setError(`Failed to load law content: ${err.message || 'Unknown error'}`);
        }
      } finally {
        setLoading(false);
      }
    };

    loadLawContent();
  }, [selectedLawId]);

  const activeLaw = laws.find(l => l.id === selectedLawId);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      {/* Dynamic Header */}
      <Header backendConnected={backendConnected} />

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          laws={laws}
          selectedLawId={selectedLawId}
          onSelectLaw={(lawId) => {
            setSelectedLawId(lawId);
            if (activeTab === 'add_law') setActiveTab('laws');
          }}
          stats={stats}
        />

        {/* Workspace Area */}
        <main className="relative flex flex-1 flex-col overflow-hidden">
          
          {/* Tabs bar */}
          <div className="flex h-12 w-full items-center justify-between border-b border-zinc-200 bg-zinc-50/50 px-6 dark:border-zinc-800 dark:bg-zinc-900/10">
            <div className="flex gap-4">
              <button
                onClick={() => setActiveTab('laws')}
                className={`flex h-12 items-center gap-2 border-b-2 px-1 text-xs font-bold transition-all ${
                  activeTab === 'laws'
                    ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                    : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                }`}
              >
                <BookOpen className="h-4 w-4" />
                <span>Law Corpus Browser</span>
              </button>
              <button
                onClick={() => setActiveTab('graph')}
                className={`flex h-12 items-center gap-2 border-b-2 px-1 text-xs font-bold transition-all ${
                  activeTab === 'graph'
                    ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                    : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                }`}
              >
                <Network className="h-4 w-4" />
                <span>Knowledge Graph Explorer</span>
              </button>
              <button
                onClick={() => setActiveTab('add_law')}
                className={`flex h-12 items-center gap-2 border-b-2 px-1 text-xs font-bold transition-all ${
                  activeTab === 'add_law'
                    ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                    : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                }`}
              >
                <PlusCircle className="h-4 w-4" />
                <span>Add & Ingest Law</span>
              </button>
            </div>

            {/* Context breadcrumb */}
            {activeLaw && (
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <ShieldCheck className="h-4 w-4 text-indigo-500" />
                <span className="font-semibold text-zinc-700 dark:text-zinc-300">{activeLaw.name}</span>
                <span>/</span>
                <span className="capitalize">{activeTab === 'add_law' ? 'Ingestion Pipeline' : `${activeTab} View`}</span>
              </div>
            )}
          </div>

          {/* Active Tab Panel */}
          <div className="flex-1 overflow-hidden">
            {error && activeTab !== 'add_law' ? (
              <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-zinc-50 dark:bg-zinc-950">
                <div className="rounded-full bg-rose-50 p-4 dark:bg-rose-950/20 text-rose-500">
                  <ShieldAlert className="h-10 w-10" />
                </div>
                <h3 className="mt-4 text-lg font-bold text-zinc-950 dark:text-white">API Connection Error</h3>
                <p className="mt-2 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
                  {error}
                </p>
                <p className="mt-4 max-w-sm text-xs leading-relaxed text-zinc-400">
                  Please ensure that your FastAPI backend is running locally on port 8000:
                  <code className="mt-2 block rounded bg-zinc-100 p-2 font-mono dark:bg-zinc-900 dark:text-zinc-350">
                    uvicorn app.main:app --reload --port 8000
                  </code>
                </p>
              </div>
            ) : activeTab === 'laws' ? (
              <LawViewer
                articles={articles}
                selectedLawId={selectedLawId}
                selectedLawName={activeLaw?.name || ''}
                activeArticleId={activeArticleId}
                onSelectArticle={setActiveArticleId}
                lawNotIngested={lawNotIngested}
              />
            ) : activeTab === 'graph' ? (
              <GraphExplorer
                graphData={graphData}
                selectedLawId={selectedLawId}
                onFetchGraph={async (lawId, limit) => {
                  const data = await getGraphData(lawId, limit);
                  setGraphData(data);
                }}
              />
            ) : (

              <AddLawTab
                onIngestionSuccess={async () => {
                  try {
                    const updatedLaws = await getLaws();
                    setLaws(updatedLaws);
                  } catch (_) {}
                }}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

