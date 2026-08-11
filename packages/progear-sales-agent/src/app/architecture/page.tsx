'use client';

import Link from 'next/link';
import { ArrowLeft, Fingerprint, ShieldCheck } from 'lucide-react';
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

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-12">
        <section className="mb-8 grid items-center gap-7 lg:grid-cols-[1.35fr,0.65fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-800 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200">
              <ShieldCheck className="h-4 w-4" /> Built around a first-class agent identity
            </div>
            <h2 className="mt-4 max-w-4xl text-3xl font-black tracking-tight text-slate-950 dark:text-white sm:text-5xl">
              Know who asked, which agent acted, and what it reached.
            </h2>
            <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600 dark:text-slate-300 sm:text-lg">
              Okta keeps the employee and the ProGear Agent visible across the entire delegated access chain. That makes every action attributable—and gives security teams one identity they can deactivate to stop new token exchanges.
            </p>
          </div>
          <div className="rounded-2xl border border-orange-200 bg-white/90 p-5 shadow-sm dark:border-orange-900 dark:bg-slate-950/80">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300">
                <Fingerprint className="h-5 w-5" />
              </span>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">The core idea</p>
                <p className="font-bold text-slate-950 dark:text-white">Two identities. One attributable action.</p>
              </div>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
              The employee is the subject. The Workload Principal identifies the agent client acting on that employee’s behalf. Neither identity replaces the other.
            </p>
          </div>
        </section>

        <D3ArchitectureDiagram />
      </div>
    </main>
  );
}
