'use client';

import React from 'react';
import { Law } from '../lib/types';
import { Book, Globe, ShieldAlert, Cpu, HardDrive, Terminal } from 'lucide-react';

interface SidebarProps {
  laws: Law[];
  selectedLawId: string;
  onSelectLaw: (lawId: string) => void;
  stats?: {
    nodes: number;
    edges: number;
    vectors: number;
  };
}

export default function Sidebar({ laws, selectedLawId, onSelectLaw, stats = { nodes: 154, edges: 312, vectors: 154 } }: SidebarProps) {
  return (
    <aside className="flex h-[calc(100vh-4rem)] w-64 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/30">
      {/* Scrollable Law List */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <h2 className="px-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          Knowledge Domains
        </h2>
        
        <nav className="mt-4 space-y-2">
          {laws.map((law) => {
            const isActive = law.id === selectedLawId;
            const isComingSoon = law.status === 'coming_soon';

            return (
              <button
                key={law.id}
                onClick={() => !isComingSoon && onSelectLaw(law.id)}
                disabled={isComingSoon}
                className={`group flex w-full flex-col rounded-xl p-3.5 text-left transition-all ${
                  isActive
                    ? 'bg-white shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-800 dark:ring-zinc-700'
                    : isComingSoon
                    ? 'opacity-60 cursor-not-allowed hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30'
                    : 'hover:bg-white/60 dark:hover:bg-zinc-800/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Book className={`h-4.5 w-4.5 ${
                      isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-zinc-400'
                    }`} />
                    <span className={`font-semibold text-sm ${
                      isActive ? 'text-zinc-900 dark:text-white' : 'text-zinc-700 dark:text-zinc-300'
                    }`}>
                      {law.name}
                    </span>
                  </div>
                  {isComingSoon && (
                    <span className="rounded bg-zinc-200 px-1.5 py-0.5 text-[9px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                      Soon
                    </span>
                  )}
                </div>
                
                <p className="mt-1 text-xs text-zinc-500 line-clamp-2 dark:text-zinc-400">
                  {law.description}
                </p>

                <div className="mt-2.5 flex items-center gap-1.5 text-[10px] font-medium text-zinc-400">
                  <Globe className="h-3 w-3" />
                  <span>{law.region}</span>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      {/* System Stats Section */}
      <div className="border-t border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="px-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          Engine Statistics
        </h3>
        
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-zinc-100/60 p-2.5 dark:bg-zinc-800/30">
            <span className="block text-[10px] text-zinc-400">Graph Nodes</span>
            <span className="mt-0.5 block font-bold text-zinc-700 dark:text-zinc-300">{stats.nodes}</span>
          </div>
          <div className="rounded-lg bg-zinc-100/60 p-2.5 dark:bg-zinc-800/30">
            <span className="block text-[10px] text-zinc-400">Graph Edges</span>
            <span className="mt-0.5 block font-bold text-zinc-700 dark:text-zinc-300">{stats.edges}</span>
          </div>
          <div className="col-span-2 rounded-lg bg-zinc-100/60 p-2.5 dark:bg-zinc-800/30 flex items-center justify-between">
            <div>
              <span className="block text-[10px] text-zinc-400">Vector Embeddings</span>
              <span className="mt-0.5 block font-bold text-zinc-700 dark:text-zinc-300">{stats.vectors}</span>
            </div>
            <HardDrive className="h-4 w-4 text-zinc-400" />
          </div>
        </div>

        {/* Developer Console Links */}
        <div className="mt-4 space-y-1">
          <a
            href="http://localhost:7474"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-zinc-800/50 dark:hover:text-white"
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>Neo4j Browser</span>
          </a>
          <a
            href="http://localhost:6333/dashboard"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-zinc-800/50 dark:hover:text-white"
          >
            <Cpu className="h-3.5 w-3.5" />
            <span>Qdrant Dashboard</span>
          </a>
        </div>
      </div>
    </aside>
  );
}
