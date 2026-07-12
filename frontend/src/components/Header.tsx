'use client';

import React from 'react';
import { Scale, Database, Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  backendConnected: boolean;
}

export default function Header({ backendConnected }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-zinc-200 bg-white/85 px-6 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/85">
      {/* Left: Logo & Branding */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-500/20">
          <Scale className="h-5 w-5" />
        </div>
        <div>
          <h1 className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-lg font-bold tracking-tight text-transparent dark:from-indigo-400 dark:to-violet-400">
            LegalGraph RAG
          </h1>
          <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            Knowledge Engine v1.0
          </span>
        </div>
      </div>

      {/* Right: API Status and Metadata */}
      <div className="flex items-center gap-4">
        {/* Status Indicator */}
        <div className="flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-50/50 px-3 py-1 text-xs font-medium text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
          <div className="relative flex h-2 w-2">
            {backendConnected ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              </>
            ) : (
              <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500"></span>
            )}
          </div>
          <span className="hidden sm:inline">
            {backendConnected ? 'Backend Connected' : 'Offline / Mock Mode'}
          </span>
          {backendConnected ? (
            <Wifi className="h-3.5 w-3.5 text-emerald-500" />
          ) : (
            <WifiOff className="h-3.5 w-3.5 text-amber-500" />
          )}
        </div>

        {/* Database Icon */}
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 shadow-sm hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800">
          <Database className="h-4 w-4" />
        </div>
      </div>
    </header>
  );
}
