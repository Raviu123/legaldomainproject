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
  Eye,
  FileText,
  Printer,
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
      const chapter = art.chapter || 'Statutory Provisions';
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
      const chapter = art.chapter || 'Statutory Provisions';
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
    return articles[0] || null;
  }, [articles, selectedArticleId]);

  // Set default selection when articles load
  useEffect(() => {
    if (articles.length > 0 && !selectedArticleId) {
      setSelectedArticleId(articles[0].id);
    }
  }, [articles, selectedArticleId]);

  // Smooth scroll to selected article in center pane when selection changes
  const scrollToArticle = (artId: string) => {
    setSelectedArticleId(artId);
    setTimeout(() => {
      const el = document.getElementById(`article-${artId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 50);
  };

  // Helper to jump to a referenced article
  const handleJumpToReference = (refId: string) => {
    const found = articles.find(
      (a) => a.id === refId || a.id.toLowerCase() === refId.toLowerCase()
    );
    if (found) {
      scrollToArticle(found.id);
    } else {
      const cleanRefId = refId.includes(':') ? refId.split(':')[1] : refId;
      const parsedFound = articles.find(
        (a) =>
          a.article?.toLowerCase().replace(/\s+/g, '') ===
            cleanRefId.toLowerCase().replace(/\s+/g, '') ||
          a.id.toLowerCase().endsWith(cleanRefId.toLowerCase())
      );
      if (parsedFound) {
        scrollToArticle(parsedFound.id);
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
        <p className="mt-4 text-base font-semibold">Loading Law Document...</p>
        <p className="text-sm text-zinc-400">Fetching text for {selectedLawName}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 overflow-hidden bg-zinc-100 dark:bg-zinc-950">
      {/* Index Column (Left Navigation Sidebar) */}
      <div className="flex w-72 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/80">
        <div className="border-b border-zinc-200 p-3.5 dark:border-zinc-800">
          <input
            type="text"
            placeholder="Filter sections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 w-full rounded-md border border-zinc-200 bg-zinc-50 px-3 text-xs outline-none focus:border-indigo-500 focus:bg-white dark:border-zinc-700 dark:bg-zinc-950 dark:focus:border-indigo-500"
          />
        </div>

        {/* Navigation List */}
        <div className="flex-1 overflow-y-auto p-2">
          {Object.entries(groupedFilteredArticles).map(([chapter, chapterArticles]) => (
            <div key={chapter} className="mb-3">
              <h3 className="sticky top-0 z-10 bg-white/95 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:bg-zinc-900">
                {chapter}
              </h3>
              <ul className="mt-0.5 space-y-0.5">
                {chapterArticles.map((art) => {
                  const isActive = art.id === activeArticle?.id;
                  return (
                    <li key={art.id}>
                      <button
                        id={`nav-${art.id}`}
                        onClick={() => scrollToArticle(art.id)}
                        className={`flex w-full items-center justify-between rounded px-2.5 py-1.5 text-left transition-all ${
                          isActive
                            ? 'bg-indigo-50 font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300'
                            : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800/40'
                        }`}
                      >
                        <span className="text-xs truncate">
                          {art.article || art.title || 'Section'}
                        </span>
                        {isActive && <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 dark:bg-indigo-400"></span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Center Column: Clean Official Document Page Area */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 flex justify-center">
        {/* Paper Sheet Container */}
        <div className="w-full max-w-3xl bg-white border border-zinc-200/80 shadow-sm rounded-none p-8 md:p-12 dark:bg-zinc-900 dark:border-zinc-800 min-h-full">
          {/* Document Official Header */}
          <header className="border-b-2 border-zinc-900 pb-6 mb-8 text-center dark:border-zinc-200">
            <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">
              OFFICIAL STATUTORY TEXT
            </span>
            <h1 className="mt-1 text-2xl md:text-3xl font-serif font-bold text-zinc-900 dark:text-white tracking-tight">
              {selectedLawName}
            </h1>
            <p className="mt-2 text-xs font-mono text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
              IDENTIFIER: {selectedLawId} • TOTAL UNITS: {articles.length}
            </p>
          </header>

          {/* Continuous Document Content Stream */}
          <main className="space-y-8 font-serif">
            {Object.entries(groupedFilteredArticles).map(([chapter, chapterArticles]) => (
              <section key={chapter} className="space-y-6">
                {/* Chapter Heading */}
                <div className="pt-4 pb-2 border-b border-zinc-200 dark:border-zinc-800">
                  <h2 className="text-sm font-sans font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                    {chapter}
                  </h2>
                </div>

                {/* Articles Stream */}
                {chapterArticles.map((art) => {
                  const isActive = art.id === activeArticle?.id;
                  return (
                    <article
                      key={art.id}
                      id={`article-${art.id}`}
                      onClick={() => setSelectedArticleId(art.id)}
                      className={`scroll-mt-6 p-4 rounded-lg transition-all duration-150 cursor-pointer ${
                        isActive
                          ? 'bg-amber-50/80 border-l-4 border-amber-500 shadow-2xs dark:bg-amber-950/20 dark:border-amber-400'
                          : 'hover:bg-zinc-50/80 dark:hover:bg-zinc-800/30'
                      }`}
                    >
                      {/* Section Title Header */}
                      <div className="flex items-baseline justify-between mb-2 font-sans">
                        <h3 className="text-sm font-bold text-zinc-900 dark:text-white flex items-center gap-2">
                          <span>{art.article || art.title || 'Section'}</span>
                          {art.title && art.article && (
                            <span className="font-normal text-zinc-600 dark:text-zinc-400">
                              — {art.title}
                            </span>
                          )}
                        </h3>
                        {art.url && (
                          <a
                            href={art.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-zinc-400 hover:text-indigo-600 text-xs font-mono"
                            title="Source link"
                          >
                            [src]
                          </a>
                        )}
                      </div>

                      {/* Official Text Body */}
                      <div className="text-sm md:text-base leading-relaxed text-zinc-800 dark:text-zinc-200 whitespace-pre-line text-justify font-serif">
                        {art.text}
                      </div>

                      {/* Definitions if present inside article */}
                      {art.definitions && art.definitions.length > 0 && (
                        <div className="mt-3 pt-2 font-sans text-xs border-t border-zinc-200/60 dark:border-zinc-800/60">
                          <span className="font-bold text-zinc-500 uppercase tracking-wider text-[10px]">
                            Definitions:
                          </span>
                          <ul className="mt-1 space-y-1">
                            {art.definitions.map((def, idx) => (
                              <li key={idx} className="text-zinc-700 dark:text-zinc-300">
                                <strong>“{def.term}”</strong>: {def.definition}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </article>
                  );
                })}
              </section>
            ))}
          </main>
        </div>
      </div>

      {/* Right sidebar (Tabbed Metadata + AI Section) */}
      <div className="w-80 border-l border-zinc-200 flex flex-col bg-white dark:border-zinc-800 dark:bg-zinc-900/80 overflow-hidden">
        {/* Sidebar Tabs Header */}
        <div className="flex border-b border-zinc-200 bg-zinc-50 p-1 dark:border-zinc-800 dark:bg-zinc-900">
          <button
            onClick={() => setRightTab('metadata')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-bold rounded transition-all ${
              rightTab === 'metadata'
                ? 'bg-white text-indigo-600 shadow-2xs dark:bg-zinc-800 dark:text-indigo-400'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Metadata</span>
          </button>
          <button
            onClick={() => setRightTab('ai')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-bold rounded transition-all ${
              rightTab === 'ai'
                ? 'bg-white text-indigo-600 shadow-2xs dark:bg-zinc-800 dark:text-indigo-400'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            <span>AI Ask</span>
          </button>
        </div>

        {/* Tab 1: Active Article Metadata Explorer */}
        {rightTab === 'metadata' && (
          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {activeArticle ? (
              <>
                {/* Active Unit Focus Summary */}
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-950">
                  <div className="flex items-center gap-2">
                    <Bookmark className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    <h4 className="text-xs font-bold text-zinc-900 dark:text-white truncate">
                      {activeArticle.article || activeArticle.title}
                    </h4>
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                    {activeArticle.chapter}
                  </p>
                </div>

                {/* Defined Terms */}
                <div>
                  <h4 className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    <HelpCircle className="h-3.5 w-3.5 text-indigo-500" />
                    Defined Terms ({activeArticle.definitions?.length || 0})
                  </h4>
                  {activeArticle.definitions && activeArticle.definitions.length > 0 ? (
                    <div className="mt-2 space-y-2">
                      {activeArticle.definitions.map((def, idx) => (
                        <div
                          key={idx}
                          className="rounded border border-zinc-200 bg-white p-2.5 dark:border-zinc-800 dark:bg-zinc-900"
                        >
                          <span className="text-xs font-bold text-zinc-900 dark:text-white">
                            “{def.term}”
                          </span>
                          <p className="mt-1 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">
                            {def.definition}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-xs text-zinc-400 italic">No definitions in section.</p>
                  )}
                </div>

                {/* Cross References */}
                <div>
                  <h4 className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    <LinkIcon className="h-3.5 w-3.5 text-indigo-500" />
                    Cross References ({activeArticle.references?.length || 0})
                  </h4>
                  {activeArticle.references && activeArticle.references.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {activeArticle.references.map((ref, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleJumpToReference(ref)}
                          className="flex items-center gap-1 rounded border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-300"
                        >
                          <span>{ref}</span>
                          <ChevronRight className="h-3 w-3" />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-xs text-zinc-400 italic">No outward cross-references.</p>
                  )}
                </div>

                {/* Semantic Concepts */}
                <div>
                  <h4 className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    <Tag className="h-3.5 w-3.5 text-indigo-500" />
                    Concepts ({activeArticle.concepts?.length || 0})
                  </h4>
                  {activeArticle.concepts && activeArticle.concepts.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {activeArticle.concepts.map((concept, idx) => (
                        <span
                          key={idx}
                          className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                        >
                          #{concept}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-xs text-zinc-400 italic">No semantic tags attached.</p>
                  )}
                </div>
              </>
            ) : (
              <p className="text-xs text-zinc-400">Select an article to view details.</p>
            )}
          </div>
        )}

        {/* Tab 2: AI Q&A Panel */}
        {rightTab === 'ai' && (
          <div className="flex-1 flex flex-col overflow-hidden p-4 space-y-4">
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {/* Question Suggestions */}
              {!aiResponse && !aiLoading && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-zinc-700 dark:text-zinc-300">
                    <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                    <span>Suggested Questions:</span>
                  </div>
                  <div className="space-y-1.5">
                    {getSuggestions(selectedLawName).map((sug, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleAiQuery(undefined, sug)}
                        className="w-full text-left rounded-lg border border-zinc-200 bg-zinc-50 p-2 text-xs text-zinc-700 hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 transition-all"
                      >
                        {sug}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Last Asked Question Header */}
              {lastAskedQuestion && (
                <div className="rounded bg-zinc-100 p-2.5 text-xs font-bold text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
                  <span className="text-[10px] text-zinc-400 block font-normal uppercase">Query</span>
                  “{lastAskedQuestion}”
                </div>
              )}

              {/* Loading State */}
              {aiLoading && (
                <div className="flex flex-col items-center justify-center py-6 text-center text-xs text-zinc-500 space-y-2">
                  <Loader2 className="h-5 w-5 animate-spin text-indigo-600 dark:text-indigo-400" />
                  <p className="font-semibold">Querying Legal Knowledge Base...</p>
                </div>
              )}

              {/* Error State */}
              {aiError && (
                <div className="rounded border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300">
                  {aiError}
                </div>
              )}

              {/* AI Response Display */}
              {aiResponse && !aiLoading && (
                <div className="space-y-3">
                  <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                        Synthesized Answer
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${getConfidenceColor(
                          aiResponse.confidence
                        )}`}
                      >
                        {(aiResponse.confidence * 100).toFixed(0)}% Confidence
                      </span>
                    </div>

                    <p className="text-xs leading-relaxed text-zinc-800 dark:text-zinc-200 whitespace-pre-line">
                      {aiResponse.answer}
                    </p>
                  </div>

                  {/* Sources / Citations */}
                  {aiResponse.sources && aiResponse.sources.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                        Citations ({aiResponse.sources.length})
                      </span>
                      {aiResponse.sources.map((src, idx) => (
                        <button
                          key={idx}
                          onClick={() => scrollToArticle(src.unit_id)}
                          className="w-full text-left rounded border border-zinc-200 bg-white p-2 hover:border-indigo-300 dark:border-zinc-800 dark:bg-zinc-900 transition-all"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                              {src.article || src.title}
                            </span>
                            <span className="text-[10px] text-zinc-400">
                              {(src.score * 100).toFixed(0)}%
                            </span>
                          </div>
                          <p className="mt-1 text-[11px] text-zinc-500 line-clamp-2 dark:text-zinc-400">
                            {src.text_snippet}
                          </p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* AI Q&A Input Box */}
            <form onSubmit={handleAiQuery} className="pt-2 border-t border-zinc-200 dark:border-zinc-800">
              <div className="relative flex items-center">
                <input
                  type="text"
                  placeholder={`Ask about ${selectedLawName}...`}
                  value={aiQuestion}
                  onChange={(e) => setAiQuestion(e.target.value)}
                  disabled={aiLoading}
                  className="w-full rounded-lg border border-zinc-300 bg-white py-2 pl-3 pr-8 text-xs font-medium text-zinc-900 placeholder-zinc-400 focus:border-indigo-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                />
                <button
                  type="submit"
                  disabled={aiLoading || !aiQuestion.trim()}
                  className="absolute right-1.5 rounded bg-indigo-600 p-1 text-white hover:bg-indigo-500 disabled:opacity-40"
                >
                  <Send className="h-3 w-3" />
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
