'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { RegistryEntry, IngestOptions } from '../lib/types';
import { getLawRegistry, triggerIngestion, triggerIngestionFile, triggerCheckUpdates, deleteLaw } from '../lib/api';
import {
  PlusCircle,
  Play,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Globe,
  Database,
  ExternalLink,
  Code,
  Layers,
  Sparkles,
  Sliders,
  FileText,
  UploadCloud,
  FileCheck,
  X,
  FilePlus,
  BookOpen,
  Trash2
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
  { identifier: 'sg_pdpa', name: 'PDPA', full_name: 'Personal Data Protection Act 2012 (Singapore)', jurisdiction: 'SG', status: 'ACTIVE', source_url: 'https://sso.agc.gov.sg/Act/PDPA2012' },
];

const JURISDICTION_NAMES: Record<string, string> = {
  EU: 'European Union (EU)',
  IN: 'India (IN)',
  UK: 'United Kingdom (UK)',
  US: 'United States (US)',
  AU: 'Australia (AU)',
  BR: 'Brazil (BR)',
  SG: 'Singapore (SG)',
  CA: 'Canada (CA)',
  JP: 'Japan (JP)',
  GLOBAL: 'Global / Other (GLOBAL)',
};

export default function AddLawTab({ onIngestionSuccess }: AddLawTabProps) {
  // Registry state
  const [registry, setRegistry] = useState<RegistryEntry[]>(DEFAULT_LAWS);
  const [loadingRegistry, setLoadingRegistry] = useState<boolean>(false);

  // Sub-Tab Mode: 'existing' | 'new'
  const [activeIngestTab, setActiveIngestTab] = useState<'existing' | 'new'>('existing');

  // Existing Law Cascading Selection State
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<string>('EU');
  const [selectedLaw, setSelectedLaw] = useState<string>('gdpr');

  // New Law Custom Form State
  const [newLawName, setNewLawName] = useState<string>('');
  const [newLawJurisdiction, setNewLawJurisdiction] = useState<string>('SG');

  // Ingestion Source Mode: 'url' | 'pdf'
  const [ingestSourceMode, setIngestSourceMode] = useState<'pdf' | 'url'>('pdf');
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // Advanced Pipeline Options
  const [skipFetch, setSkipFetch] = useState<boolean>(false);
  const [skipGraph, setSkipGraph] = useState<boolean>(false);
  const [skipVector, setSkipVector] = useState<boolean>(false);
  const [forceRecreateVector, setForceRecreateVector] = useState<boolean>(false);
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Status & Feedback state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [deletingLawId, setDeletingLawId] = useState<string | null>(null);
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
        const data = await getLawRegistry();
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

  // Compute available jurisdictions dynamically for existing laws
  const jurisdictions = useMemo(() => {
    const set = new Set<string>();
    registry.forEach((item) => set.add(item.jurisdiction));
    return Array.from(set);
  }, [registry]);

  // Compute laws available for currently selected jurisdiction
  const lawsForJurisdiction = useMemo(() => {
    return registry.filter((item) => item.jurisdiction === selectedJurisdiction);
  }, [registry, selectedJurisdiction]);

  // Handle Jurisdiction change in cascading dropdown
  const handleJurisdictionChange = (newJur: string) => {
    setSelectedJurisdiction(newJur);
    const matchingLaws = registry.filter((l) => l.jurisdiction === newJur);
    if (matchingLaws.length > 0) {
      setSelectedLaw(matchingLaws[0].identifier);
    }
  };

  // Drag & drop handlers for PDF file upload
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        setPdfFile(file);
        setFeedback(null);
      } else {
        setFeedback({ type: 'error', message: 'Please drop a valid PDF file (.pdf format).' });
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        setPdfFile(file);
        setFeedback(null);
      } else {
        setFeedback({ type: 'error', message: 'Please select a valid PDF file (.pdf format).' });
      }
    }
  };

  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFeedback(null);

    let targetLawIdentifier = selectedLaw;

    if (activeIngestTab === 'new') {
      if (!newLawName.trim()) {
        setFeedback({ type: 'error', message: 'Please enter a name or short code for the new law.' });
        setIsSubmitting(false);
        return;
      }
      targetLawIdentifier = newLawName.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    }

    if (ingestSourceMode === 'pdf' && !pdfFile) {
      setFeedback({ type: 'error', message: 'Please select or drop a PDF file to proceed with file ingestion.' });
      setIsSubmitting(false);
      return;
    }

    const payload: IngestOptions = {
      law: targetLawIdentifier,
      skip_fetch: skipFetch,
      skip_graph: skipGraph,
      skip_vector: skipVector,
      force_recreate_vector: forceRecreateVector,
      dry_run: dryRun,
    };

    try {
      let res;
      if (ingestSourceMode === 'pdf' && pdfFile) {
        res = await triggerIngestionFile(pdfFile, payload);
      } else {
        res = await triggerIngestion(payload);
      }

      setFeedback({
        type: 'success',
        message: res.message || `Ingestion job for ${targetLawIdentifier.toUpperCase()} successfully queued!`,
      });

      // Refresh registry list to show the newly added law immediately
      try {
        const freshData = await getLawRegistry();
        if (freshData && freshData.length > 0) setRegistry(freshData);
      } catch (_) {}

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
      const res = await triggerCheckUpdates(autoReingest);
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

  const handleQuickIngest = (law: RegistryEntry) => {
    setActiveIngestTab('existing');
    setSelectedJurisdiction(law.jurisdiction);
    setSelectedLaw(law.identifier);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleDeleteLaw = async (lawId: string, lawName: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to completely delete '${lawName}' (${lawId})?\n\nThis will purge data from:\n1. Neo4j Knowledge Graph\n2. Qdrant Vector DB\n3. PostgreSQL Database\n4. Raw & Normalized Disk Caches`
    );
    if (!confirmed) return;

    setDeletingLawId(lawId);
    setFeedback(null);

    try {
      const res = await deleteLaw(lawId);
      setFeedback({
        type: 'success',
        message: `Law '${lawId.toUpperCase()}' deleted successfully across Neo4j, Qdrant, PostgreSQL, and disk caches!`,
      });

      const freshData = await getLawRegistry();
      if (freshData) setRegistry(freshData);
      if (onIngestionSuccess) onIngestionSuccess();
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || `Failed to delete law '${lawId}'.`,
      });
    } finally {
      setDeletingLawId(null);
    }
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
                Trigger background ingestion, parsing, knowledge graph construction in Neo4j, and vector indexing in Qdrant for statutory legal frameworks.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={async () => {
                  setLoadingRegistry(true);
                  try {
                    const data = await getLawRegistry();
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
              {/* Header */}
              <div className="flex items-center justify-between border-b border-zinc-100 pb-4 dark:border-zinc-800">
                <div className="flex items-center gap-2">
                  <Play className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  <h3 className="font-semibold text-zinc-900 dark:text-white text-sm">
                    Ingestion Pipeline Trigger
                  </h3>
                </div>
                <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400">
                  {ingestSourceMode === 'pdf' ? 'POST /api/v1/admin/ingest-file' : 'POST /api/v1/admin/ingest'}
                </span>
              </div>

              {/* Sub-Tabs: Update Existing Law vs Ingest New Custom Law */}
              <div className="mt-4 flex border-b border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setActiveIngestTab('existing')}
                  className={`flex items-center gap-2 border-b-2 px-4 py-2 text-xs font-bold transition-all ${
                    activeIngestTab === 'existing'
                      ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                      : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200'
                  }`}
                >
                  <BookOpen className="h-3.5 w-3.5" />
                  <span>Update Catalog Law</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveIngestTab('new')}
                  className={`flex items-center gap-2 border-b-2 px-4 py-2 text-xs font-bold transition-all ${
                    activeIngestTab === 'new'
                      ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                      : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200'
                  }`}
                >
                  <FilePlus className="h-3.5 w-3.5" />
                  <span>Ingest Brand New Law (PDF / URL)</span>
                </button>
              </div>

              <form onSubmit={handleIngestSubmit} className="mt-5 space-y-5">
                {/* SUB-TAB 1: Existing Catalog Laws (Cascading Dropdowns) */}
                {activeIngestTab === 'existing' ? (
                  <div className="space-y-4">
                    {/* Cascading Dropdown 1: Jurisdiction / Region */}
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                        1. Select Jurisdiction / Region <span className="text-rose-500">*</span>
                      </label>
                      <select
                        value={selectedJurisdiction}
                        onChange={(e) => handleJurisdictionChange(e.target.value)}
                        className="w-full rounded-xl border border-zinc-300 bg-white p-2.5 text-xs font-semibold text-zinc-900 shadow-sm focus:border-indigo-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-indigo-400"
                        required
                      >
                        {jurisdictions.map((jur) => (
                          <option
                            key={jur}
                            value={jur}
                            className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100 font-medium py-1"
                          >
                            {JURISDICTION_NAMES[jur] || jur}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Cascading Dropdown 2: Target Registered Law */}
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                        2. Select Registered Catalog Law ({lawsForJurisdiction.length} available) <span className="text-rose-500">*</span>
                      </label>
                      <select
                        value={selectedLaw}
                        onChange={(e) => setSelectedLaw(e.target.value)}
                        className="w-full rounded-xl border border-zinc-300 bg-white p-2.5 text-xs font-semibold text-zinc-900 shadow-sm focus:border-indigo-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-indigo-400"
                        required
                      >
                        {lawsForJurisdiction.map((law) => (
                          <option
                            key={law.identifier}
                            value={law.identifier}
                            className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100 font-medium py-1"
                          >
                            {law.name} ({law.identifier}) — {law.full_name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                ) : (
                  /* SUB-TAB 2: New Custom Law Form */
                  <div className="space-y-4">
                    <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3 text-xs text-indigo-800 dark:border-indigo-900/40 dark:bg-indigo-950/30 dark:text-indigo-300">
                      💡 Drop any PDF file or URL for an unlisted country or new statutory framework (e.g. Singapore PDPA, Canada PIPEDA). It will be dynamically registered and structured automatically!
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                        New Law Short Name / Identifier <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. pdpa_sg, hipaa, singapore_privacy"
                        value={newLawName}
                        onChange={(e) => setNewLawName(e.target.value)}
                        className="w-full rounded-xl border border-zinc-300 bg-white p-2.5 text-xs font-semibold text-zinc-900 focus:border-indigo-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                        Select Region / Jurisdiction <span className="text-rose-500">*</span>
                      </label>
                      <select
                        value={newLawJurisdiction}
                        onChange={(e) => setNewLawJurisdiction(e.target.value)}
                        className="w-full rounded-xl border border-zinc-300 bg-white p-2.5 text-xs font-semibold text-zinc-900 focus:border-indigo-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                      >
                        {Object.entries(JURISDICTION_NAMES).map(([code, label]) => (
                          <option key={code} value={code} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {/* Ingestion Source Mode Toggle (PDF vs URL) */}
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                    Ingestion Input Format
                  </label>
                  <div className="flex rounded-xl bg-zinc-100 p-1 dark:bg-zinc-800/60">
                    <button
                      type="button"
                      onClick={() => setIngestSourceMode('pdf')}
                      className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs font-semibold transition-all ${
                        ingestSourceMode === 'pdf'
                          ? 'bg-white text-indigo-600 shadow-sm dark:bg-zinc-900 dark:text-indigo-400'
                          : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white'
                      }`}
                    >
                      <UploadCloud className="h-3.5 w-3.5" />
                      <span>Upload Local PDF File</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setIngestSourceMode('url')}
                      className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs font-semibold transition-all ${
                        ingestSourceMode === 'url'
                          ? 'bg-white text-indigo-600 shadow-sm dark:bg-zinc-900 dark:text-indigo-400'
                          : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white'
                      }`}
                    >
                      <Globe className="h-3.5 w-3.5" />
                      <span>Web Crawl (Source URL)</span>
                    </button>
                  </div>
                </div>

                {/* PDF Drag & Drop File Zone (if PDF mode selected) */}
                {ingestSourceMode === 'pdf' && (
                  <div>
                    {!pdfFile ? (
                      <div
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all cursor-pointer ${
                          isDragging
                            ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30'
                            : 'border-zinc-300 bg-zinc-50/50 hover:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-950/50'
                        }`}
                      >
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          onChange={handleFileSelect}
                          className="absolute inset-0 cursor-pointer opacity-0"
                        />
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-100 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400 mb-2">
                          <UploadCloud className="h-6 w-6" />
                        </div>
                        <p className="text-xs font-semibold text-zinc-900 dark:text-white">
                          Drag and drop PDF file here, or <span className="text-indigo-600 dark:text-indigo-400 underline">browse</span>
                        </p>
                        <p className="mt-1 text-[11px] text-zinc-500">
                          Supports legal statutory documents (.pdf). Automatically structured by AI Universal Engine.
                        </p>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between rounded-xl border border-indigo-200 bg-indigo-50/40 p-3.5 dark:border-indigo-900/50 dark:bg-indigo-950/30">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white">
                            <FileCheck className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="text-xs font-bold text-zinc-900 dark:text-white truncate max-w-xs">
                              {pdfFile.name}
                            </p>
                            <p className="text-[11px] text-zinc-500">
                              {(pdfFile.size / (1024 * 1024)).toFixed(2)} MB • PDF Document
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setPdfFile(null)}
                          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                          title="Remove PDF"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                )}

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
                          disabled={ingestSourceMode === 'pdf'}
                          className="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-semibold block">Skip Fetch</span>
                          <span className="text-[11px] text-zinc-500">
                            {ingestSourceMode === 'pdf' ? 'Automatically active when uploading a PDF file.' : 'Reuse cached raw file; skip downloading source document.'}
                          </span>
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
                      <span>
                        {activeIngestTab === 'new'
                          ? `Start Ingestion for New Law '${(newLawName || 'Custom Law').toUpperCase()}'`
                          : `Start Ingestion for '${selectedLaw.toUpperCase()}'`}
                      </span>
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

          {/* Right Column: Update Check & Developer Guide */}
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
                  Universal AI Legal Engine
                </h3>
              </div>
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                All statutory files (PDF, HTML) are now processed by the Universal AI Legal Engine.
              </p>

              <ol className="mt-3 space-y-2.5 text-xs text-zinc-600 dark:text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    1
                  </span>
                  <span>
                    Converts PDF/HTML layout to clean structured Markdown.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    2
                  </span>
                  <span>
                    Extracts chapters, articles, defined terms, and references via AI.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    3
                  </span>
                  <span>
                    Indexes directly into Neo4j Knowledge Graph & Qdrant vectors.
                  </span>
                </li>
              </ol>
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
                        onClick={() => handleQuickIngest(law)}
                        className="rounded-lg bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-700 hover:bg-indigo-50 hover:text-indigo-600 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-indigo-950 dark:hover:text-indigo-300 transition-colors"
                      >
                        Select
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteLaw(law.identifier, law.name)}
                        disabled={deletingLawId === law.identifier}
                        className="flex items-center gap-1 rounded-lg bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-600 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-400 dark:hover:bg-rose-900/60 transition-colors disabled:opacity-50"
                        title="Purge law from Neo4j, Qdrant, PostgreSQL, and disk caches"
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>{deletingLawId === law.identifier ? 'Purging...' : 'Delete'}</span>
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
