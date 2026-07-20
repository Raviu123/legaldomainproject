'use client';

import React, { useState, useEffect } from 'react';
import { RegistryEntry, IngestOptions } from '../lib/types';
import { getLawRegistry, triggerIngestion, triggerCheckUpdates } from '../lib/api';
import {
  PlusCircle,
  Play,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Key,
  Globe,
  Database,
  ExternalLink,
  Code,
  Layers,
  Sparkles,
  Sliders,
  FileText
} from 'lucide-react';

interface AddLawTabProps {
  onIngestionSuccess?: () => void;
}

const DEFAULT_LAWS: RegistryEntry[] = [
  { identifier: 'gdpr', name: 'GDPR', full_name: 'General Data Protection Regulation (EU) 2016/679', jurisdiction: 'EU', status: 'ACTIVE', source_url: 'https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng' },
  { identifier: 'dpdp', name: 'DPDP Act', full_name: 'Digital Personal Data Protection Act, 2023 (India)', jurisdiction: 'IN', status: 'ACTIVE', source_url: 'https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf' },
  { identifier: 'dpdp_rules', name: 'DPDP Rules', full_name: 'Digital Personal Data Protection Rules, 2025 (India)', jurisdiction: 'IN', status: 'ACTIVE', source_url: 'https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf' },
  { identifier: 'it_act', name: 'IT Act', full_name: 'Information Technology Act, 2000 (India)', jurisdiction: 'IN', status: 'ACTIVE', source_url: 'https://www.indiacode.nic.in/bitstream/123456789/1999/1/A2000-21%20%281%29.pdf' },
  { identifier: 'it_intermediary_rules_2021', name: 'IT Intermediary Rules', full_name: 'Information Technology (Intermediary Guidelines) Rules, 2021 (India)', jurisdiction: 'IN', status: 'ACTIVE', source_url: 'https://www.meity.gov.in' },
  { identifier: 'ai_act', name: 'AI Act', full_name: 'Artificial Intelligence Act (EU) 2024/1689', jurisdiction: 'EU', status: 'COMING_SOON', source_url: 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng' },
  { identifier: 'uk_gdpr', name: 'UK GDPR', full_name: 'UK General Data Protection Regulation', jurisdiction: 'UK', status: 'COMING_SOON', source_url: 'https://www.legislation.gov.uk/eur/2016/679/contents' },
  { identifier: 'ccpa', name: 'CCPA', full_name: 'California Consumer Privacy Act (US)', jurisdiction: 'US', status: 'COMING_SOON', source_url: 'https://leginfo.legislature.ca.gov' },
  { identifier: 'lgpd', name: 'LGPD', full_name: 'Lei Geral de Proteção de Dados (Brazil)', jurisdiction: 'BR', status: 'COMING_SOON', source_url: 'https://www.planalto.gov.br' },
  { identifier: 'privacy_act_au', name: 'Privacy Act', full_name: 'Privacy Act 1988 (Australia)', jurisdiction: 'AU', status: 'ACTIVE', source_url: 'https://www.legislation.gov.au/C2004A03712/latest/text' },
];

export default function AddLawTab({ onIngestionSuccess }: AddLawTabProps) {
  // Registry state
  const [registry, setRegistry] = useState<RegistryEntry[]>(DEFAULT_LAWS);
  const [loadingRegistry, setLoadingRegistry] = useState<boolean>(false);

  // Ingestion Form State
  const [selectedLaw, setSelectedLaw] = useState<string>('gdpr');
  const [skipFetch, setSkipFetch] = useState<boolean>(false);
  const [skipGraph, setSkipGraph] = useState<boolean>(false);
  const [skipVector, setSkipVector] = useState<boolean>(false);
  const [forceRecreateVector, setForceRecreateVector] = useState<boolean>(false);
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [adminKey, setAdminKey] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Status & Feedback state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Update check state
  const [autoReingest, setAutoReingest] = useState<boolean>(false);
  const [isCheckingUpdates, setIsCheckingUpdates] = useState<boolean>(false);
  const [updateFeedback, setUpdateFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Load backend registry on mount
  useEffect(() => {
    const fetchRegistry = async () => {
      setLoadingRegistry(true);
      try {
        const data = await getLawRegistry(adminKey || undefined);
        if (data && data.length > 0) {
          setRegistry(data);
        }
      } catch (err) {
        console.warn('Could not fetch remote registry, using built-in catalog:', err);
      } finally {
        setLoadingRegistry(false);
      }
    };
    fetchRegistry();
  }, []);

  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFeedback(null);

    const payload: IngestOptions = {
      law: selectedLaw,
      skip_fetch: skipFetch,
      skip_graph: skipGraph,
      skip_vector: skipVector,
      force_recreate_vector: forceRecreateVector,
      dry_run: dryRun,
    };

    try {
      const res = await triggerIngestion(payload, adminKey || undefined);
      setFeedback({
        type: 'success',
        message: res.message || `Ingestion job for ${selectedLaw.toUpperCase()} successfully queued!`,
      });
      if (onIngestionSuccess) onIngestionSuccess();
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to trigger ingestion process.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCheckUpdates = async () => {
    setIsCheckingUpdates(true);
    setUpdateFeedback(null);

    try {
      const res = await triggerCheckUpdates(autoReingest, adminKey || undefined);
      setUpdateFeedback({
        type: 'success',
        message: res.message || 'Source document update check queued across all active laws.',
      });
    } catch (err: any) {
      setUpdateFeedback({
        type: 'error',
        message: err.message || 'Failed to trigger update check.',
      });
    } finally {
      setIsCheckingUpdates(false);
    }
  };

  const handleQuickIngest = (lawId: string) => {
    setSelectedLaw(lawId);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="h-full overflow-y-auto bg-zinc-50 p-6 dark:bg-zinc-950">
      <div className="mx-auto max-w-6xl space-y-8 pb-12">
        {/* Banner Section */}
        <div className="relative overflow-hidden rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-500/10 via-violet-500/5 to-transparent p-6 dark:border-indigo-900/30 dark:from-indigo-950/40">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-md shadow-indigo-500/20">
                  <PlusCircle className="h-4 w-4" />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-white">
                  Law Registry & Ingestion Engine
                </h2>
              </div>
              <p className="max-w-2xl text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                Trigger background ingestion, parsing, knowledge graph construction in Neo4j, and vector indexing in Qdrant for registered statutory legal frameworks.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={async () => {
                  setLoadingRegistry(true);
                  try {
                    const data = await getLawRegistry(adminKey || undefined);
                    if (data && data.length > 0) setRegistry(data);
                  } catch (_) {}
                  setLoadingRegistry(false);
                }}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 shadow-sm hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingRegistry ? 'animate-spin' : ''}`} />
                <span>Refresh Registry</span>
              </button>
            </div>
          </div>
        </div>

        {/* Form and Side Cards Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Main Ingestion Form */}
          <div className="lg:col-span-7 space-y-6">
            <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center justify-between border-b border-zinc-100 pb-4 dark:border-zinc-800">
                <div className="flex items-center gap-2">
                  <Play className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  <h3 className="font-semibold text-zinc-900 dark:text-white text-sm">
                    Trigger Ingestion Pipeline
                  </h3>
                </div>
                <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400">
                  POST /api/v1/admin/ingest
                </span>
              </div>

              <form onSubmit={handleIngestSubmit} className="mt-5 space-y-5">
                {/* Select Law Dropdown */}
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                    Target Law Identifier <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <select
                      value={selectedLaw}
                      onChange={(e) => setSelectedLaw(e.target.value)}
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50/50 p-2.5 text-xs font-medium text-zinc-900 focus:border-indigo-500 focus:bg-white focus:outline-none dark:border-zinc-800 dark:bg-zinc-950 dark:text-white dark:focus:border-indigo-400"
                      required
                    >
                      {registry.map((law) => (
                        <option key={law.identifier} value={law.identifier}>
                          {law.name} ({law.identifier}) — {law.full_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                    Select a law registered in the backend LAW_REGISTRY dict.
                  </p>
                </div>

                {/* API Key Header field */}
                <div>
                  <label className="flex items-center gap-1 text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                    <Key className="h-3.5 w-3.5 text-zinc-400" />
                    <span>Admin Key Header (Optional in Dev)</span>
                  </label>
                  <input
                    type="password"
                    placeholder="X-Admin-Key (Leave empty for local dev)"
                    value={adminKey}
                    onChange={(e) => setAdminKey(e.target.value)}
                    className="w-full rounded-xl border border-zinc-200 bg-zinc-50/50 p-2.5 text-xs font-mono text-zinc-900 focus:border-indigo-500 focus:bg-white focus:outline-none dark:border-zinc-800 dark:bg-zinc-950 dark:text-white"
                  />
                </div>

                {/* Advanced Options Toggle */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
                  >
                    <Sliders className="h-3.5 w-3.5" />
                    <span>{showAdvanced ? 'Hide Pipeline Flags' : 'Configure Pipeline Flags'}</span>
                  </button>

                  {showAdvanced && (
                    <div className="mt-3 rounded-xl border border-zinc-100 bg-zinc-50/70 p-4 space-y-3 dark:border-zinc-800 dark:bg-zinc-950/40">
                      <label className="flex items-center gap-2.5 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={skipFetch}
                          onChange={(e) => setSkipFetch(e.target.checked)}
                          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-semibold block">Skip Fetch</span>
                          <span className="text-[11px] text-zinc-500">Reuse cached raw file; skip downloading source document.</span>
                        </div>
                      </label>

                      <label className="flex items-center gap-2.5 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={skipGraph}
                          onChange={(e) => setSkipGraph(e.target.checked)}
                          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-semibold block">Skip Graph Construction</span>
                          <span className="text-[11px] text-zinc-500">Bypass loading nodes & relationships into Neo4j graph database.</span>
                        </div>
                      </label>

                      <label className="flex items-center gap-2.5 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={skipVector}
                          onChange={(e) => setSkipVector(e.target.checked)}
                          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-semibold block">Skip Vector Indexing</span>
                          <span className="text-[11px] text-zinc-500">Bypass generating embeddings and storing in Qdrant vector DB.</span>
                        </div>
                      </label>

                      <label className="flex items-center gap-2.5 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={forceRecreateVector}
                          onChange={(e) => setForceRecreateVector(e.target.checked)}
                          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-semibold block">Force Recreate Vector Collection</span>
                          <span className="text-[11px] text-zinc-500">Wipe and recreate Qdrant collection before loading vectors.</span>
                        </div>
                      </label>

                      <label className="flex items-center gap-2.5 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={dryRun}
                          onChange={(e) => setDryRun(e.target.checked)}
                          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-semibold block">Dry Run Mode</span>
                          <span className="text-[11px] text-zinc-500">Parse and enrich only — do not persist changes to databases.</span>
                        </div>
                      </label>
                    </div>
                  )}
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-500/20 transition-all hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      <span>Triggering Background Ingestion...</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-current" />
                      <span>Start Ingestion Pipeline for {selectedLaw.toUpperCase()}</span>
                    </>
                  )}
                </button>
              </form>

              {/* Feedback box */}
              {feedback && (
                <div
                  className={`mt-4 flex items-start gap-3 rounded-xl p-3.5 text-xs ${
                    feedback.type === 'success'
                      ? 'border border-emerald-200 bg-emerald-50/80 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300'
                      : 'border border-rose-200 bg-rose-50/80 text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300'
                  }`}
                >
                  {feedback.type === 'success' ? (
                    <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  ) : (
                    <AlertCircle className="h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" />
                  )}
                  <p className="leading-relaxed font-medium">{feedback.message}</p>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Update Check & Codebase Guide */}
          <div className="lg:col-span-5 space-y-6">
            {/* Update Checker Card */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center gap-2 border-b border-zinc-100 pb-3 dark:border-zinc-800">
                <RefreshCw className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                <h3 className="font-semibold text-zinc-900 dark:text-white text-sm">
                  Check Document Source Updates
                </h3>
              </div>
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                Scan remote source URLs across all active laws for modifications or legal amendments.
              </p>

              <div className="mt-4 space-y-3">
                <label className="flex items-center gap-2 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoReingest}
                    onChange={(e) => setAutoReingest(e.target.checked)}
                    className="h-4 w-4 rounded border-zinc-300 text-violet-600 focus:ring-violet-500"
                  />
                  <span className="font-medium">Auto-reingest if changes detected</span>
                </label>

                <button
                  type="button"
                  onClick={handleCheckUpdates}
                  disabled={isCheckingUpdates}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-semibold text-zinc-800 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
                >
                  {isCheckingUpdates ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Checking Remote Sources...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5 text-violet-500" />
                      <span>Check Active Laws for Updates</span>
                    </>
                  )}
                </button>

                {updateFeedback && (
                  <div
                    className={`mt-2 flex items-start gap-2 rounded-lg p-2.5 text-[11px] ${
                      updateFeedback.type === 'success'
                        ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
                        : 'bg-rose-50 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300'
                    }`}
                  >
                    <p className="font-medium">{updateFeedback.message}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Developer Guide Card */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center gap-2 border-b border-zinc-100 pb-3 dark:border-zinc-800">
                <Code className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                <h3 className="font-semibold text-zinc-900 dark:text-white text-sm">
                  Adding New Custom Law
                </h3>
              </div>
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                To register a brand new statutory law into the LegalGraph engine:
              </p>

              <ol className="mt-3 space-y-2.5 text-xs text-zinc-600 dark:text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    1
                  </span>
                  <span>
                    Add identifier enum in <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[11px] dark:bg-zinc-800">app/core/constants.py</code>
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    2
                  </span>
                  <span>
                    Register metadata & parser module in <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[11px] dark:bg-zinc-800">LAW_REGISTRY</code>
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    3
                  </span>
                  <span>
                    Implement raw HTML/PDF parser in <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[11px] dark:bg-zinc-800">app/ingestion/parsers/</code>
                  </span>
                </li>
              </ol>

              <div className="mt-4 rounded-xl bg-zinc-900 p-3 font-mono text-[11px] text-zinc-300 overflow-x-auto dark:bg-zinc-950">
                <div className="text-zinc-500"># Example entry in LAW_REGISTRY:</div>
                <div className="text-indigo-400">LawIdentifier.MY_LAW: &#123;</div>
                <div className="pl-3 text-emerald-400">&quot;name&quot;: &quot;My Law 2026&quot;,</div>
                <div className="pl-3 text-emerald-400">&quot;jurisdiction&quot;: Jurisdiction.EU,</div>
                <div className="pl-3 text-emerald-400">&quot;status&quot;: LawStatus.ACTIVE,</div>
                <div className="pl-3 text-emerald-400">&quot;source_url&quot;: &quot;https://...&quot;</div>
                <div className="text-indigo-400">&#125;</div>
              </div>
            </div>
          </div>
        </div>

        {/* Registered Catalog Grid */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              <h3 className="text-base font-bold text-zinc-900 dark:text-white">
                Backend Law Registry ({registry.length})
              </h3>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {registry.map((law) => {
              const isActive = law.status === 'ACTIVE' || law.status === 'active';
              return (
                <div
                  key={law.identifier}
                  className="flex flex-col justify-between rounded-xl border border-zinc-200 bg-white p-4 transition-all hover:border-zinc-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                        {law.identifier}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          isActive
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                            : 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'
                        }`}
                      >
                        {law.status}
                      </span>
                    </div>

                    <h4 className="font-semibold text-sm text-zinc-900 dark:text-white">
                      {law.name}
                    </h4>

                    <p className="text-xs text-zinc-500 line-clamp-2 dark:text-zinc-400">
                      {law.full_name}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1 text-zinc-500">
                      <Globe className="h-3 w-3" />
                      <span>{law.jurisdiction}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      {law.source_url && (
                        <a
                          href={law.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                          title="Source Document URL"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      )}
                      <button
                        onClick={() => handleQuickIngest(law.identifier)}
                        className="rounded-lg bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-700 hover:bg-indigo-50 hover:text-indigo-600 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-indigo-950 dark:hover:text-indigo-300 transition-colors"
                      >
                        Ingest
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
