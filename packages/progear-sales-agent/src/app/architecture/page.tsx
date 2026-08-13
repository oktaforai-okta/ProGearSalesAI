'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import D3ArchitectureDiagram from '@/components/D3ArchitectureDiagram';

export default function ArchitecturePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <header className="bg-black/30 backdrop-blur-md border-b border-white/10">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="p-2 bg-white/10 hover:bg-accent/40 text-white rounded-lg transition border border-white/20 hover:border-accent/50 flex items-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="text-sm">Back to Chat</span>
            </Link>
            <div>
              <h1 className="text-white text-xl font-bold">Architecture</h1>
              <p className="text-gray-300 text-xs">
                An interactive look at identity, access, and governance for AI agents
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto py-8 px-6">
        <D3ArchitectureDiagram />
      </div>
    </main>
  );
}
