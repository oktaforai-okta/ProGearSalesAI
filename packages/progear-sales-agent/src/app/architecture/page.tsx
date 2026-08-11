'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import D3ArchitectureDiagram from '@/components/D3ArchitectureDiagram';
import { ThemeSelector } from '@/components/ThemeProvider';

export default function ArchitecturePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/50 to-orange-50/40 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <header className="border-b border-slate-200/80 bg-white/85 backdrop-blur-md dark:border-slate-800 dark:bg-slate-950/85">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-700 transition hover:border-orange-300 hover:text-orange-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-orange-700 dark:hover:text-orange-300"
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="hidden text-sm sm:inline">Back to Chat</span>
            </Link>
            <div>
              <h1 className="text-base font-bold text-slate-950 dark:text-white sm:text-lg">Secure AI Agent Architecture</h1>
              <p className="hidden text-xs text-slate-500 dark:text-slate-400 sm:block">Identity, delegation, authorization, and control</p>
            </div>
          </div>
          <ThemeSelector />
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-7 sm:px-6 sm:py-9">
        <section className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">ProGear security model</p>
            <h2 className="mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">User → agent → authorized resource</h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Okta governs identity and token exchange. FGA adds the optional Inventory decision.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px] font-semibold text-slate-600 dark:text-slate-300">
            <span className="rounded-full border border-slate-300 px-3 py-1.5 dark:border-slate-700">Workload Principal</span>
            <span className="rounded-full border border-slate-300 px-3 py-1.5 dark:border-slate-700">ID-JAG</span>
            <span className="rounded-full border border-slate-300 px-3 py-1.5 dark:border-slate-700">Scoped tokens</span>
          </div>
        </section>

        <D3ArchitectureDiagram />
      </div>
    </main>
  );
}
