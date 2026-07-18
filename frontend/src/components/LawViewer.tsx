'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { LegalUnit, AskResponse } from '../lib/types';
import { askQuestion } from '../lib/api';
import {
  BookOpen,
  ExternalLink,
  Link as LinkIcon,
  HelpCircle,
  Tag,
  Layers,
  Sparkles,
  Send,
  Loader2,
  AlertCircle,
  Bookmark,
  ChevronRight,
  CheckCircle2,
  Trash2,
} from 'lucide-react';

interface LawViewerProps {
  articles: LegalUnit[];
  selectedLawId: string;
  selectedLawName: string;
  activeArticleId?: string;
  onSelectArticle?: (id: string) => void;
  lawNotIngested?: boolean;
}

export default function LawViewer({
  articles,
  selectedLawId,
  selectedLawName,
  activeArticleId,
  onSelectArticle,
  lawNotIngested = false,
}: LawViewerProps) {
  const [internalSelectedArticleId, setInternalSelectedArticleId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Right sidebar tabs state
  const [rightTab, setRightTab] = useState<'metadata' | 'ai'>('metadata');

  // AI Q&A state
  const [aiQuestion, setAiQuestion] = useState('');
  const [lastAskedQuestion, setLastAskedQuestion] = useState('');
  const [aiResponse, setAiResponse] = useState<AskResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const selectedArticleId =
    activeArticleId !== undefined ? activeArticleId : internalSelectedArticleId;
  const setSelectedArticleId =
    onSelectArticle !== undefined ? onSelectArticle : setInternalSelectedArticleId;

  // Group articles by Chapter
  const groupedArticles = useMemo(() => {
    const groups: Record<string, LegalUnit[]> = {};
    articles.forEach((art) => {
      const chapter = art.chapter || 'Other';
      if (!groups[chapter]) {
        groups[chapter] = [];
      }
      groups[chapter].push(art);
    });
    return groups;
  }, [articles]);

  // Flattened articles that match search query
  const filteredArticles = useMemo(() => {
    if (!searchQuery.trim()) return articles;
    return articles.filter(
      (art) =>
        (art.title && art.title.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (art.article && art.article.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (art.text && art.text.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (art.concepts &&
          art.concepts.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase())))
    );
  }, [articles, searchQuery]);

  // Grouped search results
  const groupedFilteredArticles = useMemo(() => {
    const groups: Record<string, LegalUnit[]> = {};
    filteredArticles.forEach((art) => {
      const chapter = art.chapter || 'Other';
      if (!groups[chapter]) {
        groups[chapter] = [];
      }
      groups[chapter].push(art);
    });
    return groups;
  }, [filteredArticles]);

  // Get active article
  const activeArticle = useMemo(() => {
    if (selectedArticleId) {
      const found = articles.find((art) => art.id === selectedArticleId);
      if (found) return found;
    }
    // Default to first article if none selected
    return articles[0] || null;
  }, [articles, selectedArticleId]);

  // Set default selection when articles load
  useEffect(() => {
    if (articles.length > 0 && !selectedArticleId) {
      setSelectedArticleId(articles[0].id);
    }
  }, [articles, selectedArticleId]);

  // Helper to jump to a referenced article
  const handleJumpToReference = (refId: string) => {
    const found = articles.find(
      (a) => a.id === refId || a.id.toLowerCase() === refId.toLowerCase()
    );
    if (found) {
      setSelectedArticleId(found.id);
      // Scroll list item into view if possible
      const el = document.getElementById(`nav-${found.id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    } else {
      // Parse simple identifiers like "Article 6" from "gdpr:art6" to try and jump
      const cleanRefId = refId.includes(':') ? refId.split(':')[1] : refId;
      const parsedFound = articles.find(
        (a) =>
          a.article?.toLowerCase().replace(/\s+/g, '') ===
            cleanRefId.toLowerCase().replace(/\s+/g, '') ||
          a.id.toLowerCase().endsWith(cleanRefId.toLowerCase())
      );
      if (parsedFound) {
        setSelectedArticleId(parsedFound.id);
        const el = document.getElementById(`nav-${parsedFound.id}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      } else {
        alert(`Referenced unit "${refId}" is outside the loaded ${selectedLawName} subset.`);
      }
    }
  };

  // Map selectedLawId to backend parameter format
  const backendLawFilter = useMemo(() => {
    return selectedLawId ? selectedLawId.toUpperCase() : undefined;
  }, [selectedLawId]);

  // Get Suggestions based on active law
  const getSuggestions = (lawName: string) => {
    const lower = lawName.toLowerCase();
    if (lower.includes('gdpr')) {
      return [
        'What is consent under GDPR?',
        'What are the administrative fines?',
        'What is the right to be forgotten?',
      ];
    } else if (lower.includes('dpdp')) {
      return [
        'Can personal data be transferred outside India?',
        'What is a consent manager?',
        'What is the penalty for non-compliance?',
      ];
    } else if (lower.includes('ai')) {
      return [
        'What are high-risk AI systems?',
        'What are prohibited AI practices?',
        'What is the penalty structure in the AI Act?',
      ];
    } else if (lower.includes('it act') || lower.includes('information technology')) {
      return [
        'What is the penalty for failure to protect sensitive data under Section 43A?',
        'What are the powers of the government to block websites under Section 69A?',
        'What protection does Section 79 offer to social media intermediaries?',
      ];
    }
    return [
      'What is the scope of this law?',
      'What are the definitions in this act?',
      'What are the penalties for violations?',
    ];
  };

  // Handle Q&A Submission
  const handleAiQuery = async (e?: React.FormEvent, customQuestion?: string) => {
    if (e) e.preventDefault();
    const queryStr = customQuestion || aiQuestion;
    if (!queryStr.trim() || aiLoading) return;

    setAiLoading(true);
    setAiError(null);
    setLastAskedQuestion(queryStr);
    
    if (!customQuestion) {
      setAiQuestion('');
    }

    try {
      const response = await askQuestion(queryStr, backendLawFilter);
      setAiResponse(response);
    } catch (err: any) {
      console.error('Error asking AI:', err);
      setAiError(err.message || 'Failed to fetch AI response.');
    } finally {
      setAiLoading(false);
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'text-emerald-500 bg-emerald-50 dark:bg-emerald-950/20';
    if (score >= 0.5) return 'text-amber-500 bg-amber-50 dark:bg-amber-950/20';
    return 'text-rose-500 bg-rose-50 dark:bg-rose-950/20';
  };

  const getConfidenceBarColor = (score: number) => {
    if (score >= 0.8) return 'bg-emerald-500';
    if (score >= 0.5) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  if (lawNotIngested) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-500 bg-zinc-50 dark:bg-zinc-950/20">
        <AlertCircle className="h-12 w-12 text-zinc-450 dark:text-zinc-500 mb-4" />
        <h3 className="text-base font-bold text-zinc-900 dark:text-white">Law Not Ingested</h3>
        <p className="mt-2 max-w-sm text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
          The legal corpus for <b>{selectedLawName}</b> has not been ingested yet.
          Please run the ingestion pipeline first to make it active and searchable.
        </p>
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center text-zinc-500">
        <BookOpen className="h-12 w-12 animate-pulse text-zinc-300 animate-duration-1000" />
        <p className="mt-4 text-base font-semibold">Loading Law Corpus...</p>
        <p className="text-sm text-zinc-400">Fetching articles for {selectedLawName}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 overflow-hidden">
      {/* Index Column */}
      <div className="flex w-80 flex-col border-r border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/10">
        {/* Sub-search */}
        <div className="border-b border-zinc-200 p-4 dark:border-zinc-800">
          <input
            type="text"
            placeholder="Search articles & recitals..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-lg border border-zinc-200 bg-white px-3 text-xs outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-900 dark:focus:border-indigo-500"
          />
        </div>

        {/* Navigation List */}
        <div className="flex-1 overflow-y-auto p-2">
          {Object.entries(groupedFilteredArticles).map(([chapter, chapterArticles]) => (
            <div key={chapter} className="mb-4">
              <h3 className="sticky top-0 z-10 bg-zinc-50 px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:bg-zinc-950 dark:text-zinc-400">
                {chapter}
              </h3>
              <ul className="mt-1 space-y-0.5">
                {chapterArticles.map((art) => {
                  const isActive = art.id === activeArticle?.id;
                  return (
                    <li key={art.id}>
                      <button
                        id={`nav-${art.id}`}
                        onClick={() => setSelectedArticleId(art.id)}
                        className={`flex w-full flex-col rounded-lg px-3 py-2 text-left transition-all ${
                          isActive
                            ? 'bg-indigo-50 text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-300'
                            : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800/40'
                        }`}
                      >
                        <span className="text-xs font-semibold">
                          {art.article || art.title || 'Section'}
                        </span>
                        {art.title && art.article && (
                          <span
                            className={`text-[10px] truncate ${
                              isActive
                                ? 'text-indigo-700/80 dark:text-indigo-400/80'
                                : 'text-zinc-500'
                            }`}
                          >
                            {art.title}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {filteredArticles.length === 0 && (
            <div className="py-8 text-center text-xs text-zinc-400">No matching articles found</div>
          )}
        </div>
      </div>

      {/* Reading Pane Column */}
      {activeArticle && (
        <div className="flex flex-1 overflow-hidden">
          {/* Main text pane */}
          <div className="flex-1 overflow-y-auto px-8 py-6">
            <div className="mx-auto max-w-2xl">
              {/* Heading */}
              <div className="flex items-start justify-between border-b border-zinc-200 pb-4 dark:border-zinc-800">
                <div>
                  <span className="rounded bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold tracking-wider text-indigo-700 dark:bg-indigo-950 dark:text-indigo-400">
                    {activeArticle.law} • {activeArticle.chapter}
                  </span>
                  <h2 className="mt-2 text-2xl font-bold text-zinc-900 dark:text-white">
                    {activeArticle.article || activeArticle.title}
                  </h2>
                  {activeArticle.article && activeArticle.title && (
                    <p className="mt-1 text-sm font-medium text-zinc-500 dark:text-zinc-400">
                      {activeArticle.title}
                    </p>
                  )}
                </div>
                <a
                  href={activeArticle.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-50 hover:text-zinc-950 dark:border-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-white"
                >
                  <span>Official Text</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              {/* Text Body */}
              <div className="prose prose-zinc mt-6 dark:prose-invert max-w-none">
                <p className="whitespace-pre-line text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
                  {activeArticle.text}
                </p>
              </div>

              {/* In-Line Definitions */}
              {activeArticle.definitions && activeArticle.definitions.length > 0 && (
                <div className="mt-8 border-t border-zinc-200 pt-6 dark:border-zinc-800">
                  <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    <HelpCircle className="h-4 w-4 text-indigo-500" />
                    Definitions in this unit
                  </h4>
                  <dl className="mt-4 space-y-4">
                    {activeArticle.definitions.map((def, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl border border-zinc-200 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30"
                      >
                        <dt className="text-xs font-bold text-zinc-900 dark:text-white">
                          “{def.term}”
                        </dt>
                        <dd className="mt-1.5 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                          {def.definition}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </div>
          </div>

          {/* Right sidebar (Tabbed Metadata + AI Section) */}
          <div className="w-[380px] border-l border-zinc-200 flex flex-col bg-zinc-50/20 dark:border-zinc-800 dark:bg-zinc-900/5 overflow-hidden">
            {/* Sidebar Tabs Header */}
            <div className="flex border-b border-zinc-200 bg-zinc-100/50 p-1.5 dark:border-zinc-800 dark:bg-zinc-900/40">
              <button
                onClick={() => setRightTab('metadata')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-bold rounded-lg transition-all ${
                  rightTab === 'metadata'
                    ? 'bg-white text-indigo-600 shadow-sm dark:bg-zinc-800 dark:text-indigo-400'
                    : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                }`}
              >
                <Layers className="h-3.5 w-3.5" />
                <span>Explorer</span>
              </button>
              <button
                onClick={() => setRightTab('ai')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-bold rounded-lg transition-all ${
                  rightTab === 'ai'
                    ? 'bg-white text-indigo-600 shadow-sm dark:bg-zinc-800 dark:text-indigo-400'
                    : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                }`}
              >
                <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                <span>AI Q&A</span>
              </button>
            </div>

            {/* Tab Panels */}
            <div className="flex-1 overflow-y-auto">
              {rightTab === 'metadata' ? (
                /* Tab 1: Metadata Explorer (Concepts & References) */
                <div className="p-6 space-y-6">
                  {/* Concepts Tag Section */}
                  <div>
                    <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                      <Tag className="h-3.5 w-3.5" />
                      Semantic Concepts
                    </h3>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {activeArticle.concepts && activeArticle.concepts.length > 0 ? (
                        activeArticle.concepts.map((concept, idx) => (
                          <span
                            key={idx}
                            className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                          >
                            {concept}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs italic text-zinc-400">
                          No concepts extracted yet
                        </span>
                      )}
                    </div>
                  </div>

                  {/* References Section */}
                  <div>
                    <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                      <LinkIcon className="h-3.5 w-3.5" />
                      Graph References
                    </h3>
                    <div className="mt-3 space-y-1.5">
                      {activeArticle.references && activeArticle.references.length > 0 ? (
                        activeArticle.references.map((ref, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleJumpToReference(ref)}
                            className="flex w-full items-center justify-between rounded-lg border border-zinc-200 bg-white px-3 py-2 text-left text-xs font-medium text-zinc-700 shadow-sm transition-all hover:bg-zinc-50 hover:text-indigo-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-indigo-400"
                          >
                            <span className="truncate">{ref}</span>
                            <Layers className="h-3.5 w-3.5 text-zinc-400" />
                          </button>
                        ))
                      ) : (
                        <span className="text-xs italic text-zinc-400">No references listed</span>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                /* Tab 2: AI Q&A Panel */
                <div className="flex flex-col h-full bg-white dark:bg-zinc-950">
                  {aiLoading ? (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center h-full min-h-[300px]">
                      <Loader2 className="h-8 w-8 animate-spin text-indigo-500 mb-3" />
                      <span className="text-xs font-bold text-zinc-700 dark:text-zinc-300">
                        Consulting RAG Pipeline...
                      </span>
                      <span className="text-[10px] text-zinc-400 mt-1.5 max-w-[200px] leading-normal">
                        Retrieving relevant law nodes, traversing graph relationships & generating
                        cited response.
                      </span>
                    </div>
                  ) : aiResponse ? (
                    /* AI Answer View */
                    <div className="flex-1 p-5 space-y-5 overflow-y-auto">
                      {/* Close / Reset Answer Panel Button */}
                      <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-400">
                          Active Session
                        </span>
                        <button
                          onClick={() => setAiResponse(null)}
                          className="flex items-center gap-1 text-[10px] font-bold text-rose-500 hover:text-rose-600 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          <span>Clear session</span>
                        </button>
                      </div>

                      {/* Question */}
                      <div className="rounded-xl bg-zinc-50 p-3.5 dark:bg-zinc-900/40">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-400">
                          Question
                        </span>
                        <p className="mt-1 text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                          “{lastAskedQuestion}”
                        </p>
                      </div>

                      {/* Confidence Score */}
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="font-bold uppercase tracking-wider text-zinc-400">
                            Confidence Score
                          </span>
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${getConfidenceColor(
                              aiResponse.confidence
                            )}`}
                          >
                            {Math.round(aiResponse.confidence * 100)}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-zinc-100 dark:bg-zinc-800">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${getConfidenceBarColor(
                              aiResponse.confidence
                            )}`}
                            style={{ width: `${Math.round(aiResponse.confidence * 100)}%` }}
                          />
                        </div>
                      </div>

                      {/* Synthesized Answer */}
                      <div className="space-y-1.5">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-400 block">
                          Synthesized Answer
                        </span>
                        <div className="rounded-xl border border-indigo-50/50 bg-indigo-50/5 p-4 dark:border-indigo-950/20 dark:bg-indigo-950/5 leading-relaxed text-xs text-zinc-800 dark:text-zinc-200 whitespace-pre-line font-medium prose prose-zinc dark:prose-invert">
                          {aiResponse.answer}
                        </div>
                      </div>

                      {/* Cited Sources */}
                      <div className="space-y-2">
                        <span className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400">
                          Cited Sources
                        </span>
                        {aiResponse.sources.length > 0 ? (
                          <div className="space-y-1.5">
                            {aiResponse.sources.map((source, idx) => (
                              <button
                                key={idx}
                                onClick={() => handleJumpToReference(source.id)}
                                className="group flex w-full items-center justify-between rounded-xl border border-zinc-200 bg-white p-3 shadow-sm transition-all hover:border-indigo-200 hover:bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-indigo-900"
                              >
                                <div className="flex items-center gap-2.5">
                                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400">
                                    <Bookmark className="h-3.5 w-3.5" />
                                  </div>
                                  <div className="text-left">
                                    <span className="block text-[11px] font-bold text-zinc-800 dark:text-zinc-200 leading-none">
                                      {source.article || source.id}
                                    </span>
                                    <span className="text-[9px] text-zinc-400">
                                      {source.law} • Match {Math.round(source.score * 100)}%
                                    </span>
                                  </div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-zinc-400 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500" />
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 text-[10px] text-amber-500 bg-amber-50/20 p-2.5 rounded-lg">
                            <AlertCircle className="h-3.5 w-3.5" />
                            <span>No direct citations found in response context.</span>
                          </div>
                        )}
                      </div>

                      {/* Related Laws */}
                      {aiResponse.related_laws && aiResponse.related_laws.length > 0 && (
                        <div className="space-y-1.5">
                          <span className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400">
                            Related Legislation
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {aiResponse.related_laws.map((law, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 rounded bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                              >
                                <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                                {law}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Initial Onboarding / Suggestion Prompts View */
                    <div className="flex-1 flex flex-col justify-center p-6 h-full min-h-[300px]">
                      <div className="text-center mb-6">
                        <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400 mb-3">
                          <Sparkles className="h-5 w-5 animate-pulse" />
                        </div>
                        <h4 className="text-xs font-bold text-zinc-950 dark:text-white">
                          Ask Legal AI
                        </h4>
                        <p className="mt-1 text-[10px] text-zinc-500 leading-normal max-w-[220px] mx-auto">
                          Ask a question scoped to the <b>{selectedLawName}</b> corpus and receive
                          answers with graph-validated sources.
                        </p>
                      </div>

                      <div className="space-y-2">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-450 block text-left">
                          Suggested Questions
                        </span>
                        {getSuggestions(selectedLawName).map((s, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleAiQuery(undefined, s)}
                            className="w-full text-left px-3 py-2.5 rounded-xl border border-zinc-200 bg-white hover:bg-zinc-50/50 text-[10px] font-semibold text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800/40 transition-all leading-normal flex justify-between items-center group shadow-sm hover:border-indigo-200 dark:hover:border-indigo-900"
                          >
                            <span className="truncate max-w-[260px]">{s}</span>
                            <ChevronRight className="h-3 w-3 text-zinc-400 group-hover:text-indigo-500 transition-colors" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Message Input Form */}
                  <form
                    onSubmit={handleAiQuery}
                    className="border-t border-zinc-200 p-4 bg-zinc-50/30 dark:border-zinc-800 dark:bg-zinc-950"
                  >
                    <div className="relative">
                      <input
                        type="text"
                        placeholder={`Ask about ${selectedLawName}...`}
                        value={aiQuestion}
                        onChange={(e) => setAiQuestion(e.target.value)}
                        disabled={aiLoading}
                        className="h-10 w-full rounded-xl border border-zinc-200 bg-white pl-3.5 pr-10 text-xs outline-none transition-all placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-900 dark:focus:border-indigo-500"
                      />
                      <button
                        type="submit"
                        disabled={aiLoading || !aiQuestion.trim()}
                        className="absolute inset-y-1.5 right-1.5 flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-zinc-100 disabled:text-zinc-400 dark:bg-indigo-500 dark:hover:bg-indigo-600 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600 transition-colors"
                      >
                        <Send className="h-3 w-3" />
                      </button>
                    </div>
                  </form>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
