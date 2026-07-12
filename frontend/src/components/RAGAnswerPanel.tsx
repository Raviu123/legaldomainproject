'use client';

import React from 'react';
import { AskResponse } from '../lib/types';
import { X, Sparkles, AlertCircle, Bookmark, CheckCircle2, ChevronRight } from 'lucide-react';

interface RAGAnswerPanelProps {
  response: AskResponse | null;
  question: string;
  onClose: () => void;
  onNavigateToSource: (sourceId: string) => void;
}

export default function RAGAnswerPanel({ response, question, onClose, onNavigateToSource }: RAGAnswerPanelProps) {
  if (!response) return null;

  const confidencePercentage = Math.round(response.confidence * 100);

  // Determine color coding for confidence score
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

  return (
    <div className="absolute inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l border-zinc-200 bg-white shadow-2xl transition-all duration-300 ease-in-out dark:border-zinc-800 dark:bg-zinc-950">
      {/* Panel Header */}
      <div className="flex h-16 items-center justify-between border-b border-zinc-100 px-6 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-indigo-500 animate-pulse" />
          <h3 className="text-sm font-bold text-zinc-950 dark:text-white">AI Search Answer</h3>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Panel Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Question Asked */}
        <div className="rounded-xl bg-zinc-50 p-4 dark:bg-zinc-900/40">
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Question</span>
          <p className="mt-1 text-sm font-semibold text-zinc-800 dark:text-zinc-200">
            “{question}”
          </p>
        </div>

        {/* Confidence Meter */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Answer Confidence</span>
            <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${getConfidenceColor(response.confidence)}`}>
              {confidencePercentage}%
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ${getConfidenceBarColor(response.confidence)}`}
              style={{ width: `${confidencePercentage}%` }}
            ></div>
          </div>
        </div>

        {/* Generated Answer */}
        <div className="space-y-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Synthesized Answer</span>
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/10 p-5 dark:border-indigo-950/20 dark:bg-indigo-950/5">
            <p className="text-sm leading-relaxed text-zinc-800 dark:text-zinc-200 whitespace-pre-line">
              {response.answer}
            </p>
          </div>
        </div>

        {/* Citations/Sources */}
        <div className="space-y-3">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-zinc-400">Cited Sources</span>
          
          {response.sources.length > 0 ? (
            <div className="space-y-2">
              {response.sources.map((source, idx) => (
                <div
                  key={idx}
                  onClick={() => onNavigateToSource(source.id)}
                  className="group flex cursor-pointer items-center justify-between rounded-xl border border-zinc-100 bg-white p-3.5 shadow-sm transition-all hover:border-indigo-200 hover:bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/30 dark:hover:border-indigo-900"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400">
                      <Bookmark className="h-4 w-4" />
                    </div>
                    <div>
                      <span className="block text-xs font-bold text-zinc-800 dark:text-zinc-200">
                        {source.id}
                      </span>
                      <span className="text-[10px] text-zinc-400">
                        {source.law} Source
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-zinc-400 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500" />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-amber-500 bg-amber-50/50 p-3 rounded-lg">
              <AlertCircle className="h-4 w-4" />
              <span>No direct citations found for this answer.</span>
            </div>
          )}
        </div>

        {/* Related Laws metadata */}
        {response.related_laws && response.related_laws.length > 0 && (
          <div className="space-y-2">
            <span className="block text-[10px] font-bold uppercase tracking-wider text-zinc-400">Related Laws referenced</span>
            <div className="flex flex-wrap gap-1.5">
              {response.related_laws.map((law, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 rounded bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  {law}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
