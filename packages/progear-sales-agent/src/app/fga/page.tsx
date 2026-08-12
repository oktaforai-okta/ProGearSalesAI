'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import FGAExplanationCard from '@/components/FGAExplanationCard';
import FGAControlsPanel from '@/components/FGAControlsPanel';
import { ThemeSelector } from '@/components/ThemeProvider';

const FGA_CHECKS_STORAGE_KEY = 'progear-fga-checks';
const AUTHORIZATION_DECISIONS_STORAGE_KEY = 'progear-authorization-decisions';

// Reads the exact same sessionStorage the chat page (/) already writes on
// every response - no backend or API changes needed to power this page.
export default function FGAPage() {
  const [fgaChecks, setFgaChecks] = useState<any[]>([]);
  const [authorizationDecisions, setAuthorizationDecisions] = useState<any[]>([]);

  const loadFromStorage = () => {
    try {
      const checks = sessionStorage.getItem(FGA_CHECKS_STORAGE_KEY);
      const decisions = sessionStorage.getItem(AUTHORIZATION_DECISIONS_STORAGE_KEY);
      if (checks) setFgaChecks(JSON.parse(checks));
      if (decisions) setAuthorizationDecisions(JSON.parse(decisions));
    } catch (e) {
      console.error('Error loading FGA data:', e);
    }
  };

  useEffect(() => {
    loadFromStorage();
    const onFocus = () => loadFromStorage();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);

  const hasDelegationStop = authorizationDecisions.some(
    (decision) => decision.engine === 'Okta delegation policy'
  );

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-neutral-bg dark:to-primary">
      <header className="bg-gradient-to-r from-primary via-court-brown to-primary-light border-b-4 border-accent shadow-lg">
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
              <h1 className="text-white text-xl font-bold">Fine-Grained Authorization (FGA) Architecture</h1>
              <p className="text-gray-300 text-xs">Role levels, isolated demo context, and approval routing</p>
            </div>
          </div>
          <ThemeSelector />
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <FGAControlsPanel onApplied={loadFromStorage} />

        <FGAExplanationCard checks={fgaChecks} decisions={authorizationDecisions} />

        {fgaChecks.length === 0 && hasDelegationStop ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-center text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            No FGA check was made because Okta stopped delegation before ID-JAG.
          </div>
        ) : null}

        {fgaChecks.length === 0 && !hasDelegationStop ? (
          <div className="py-12 text-center text-gray-400 dark:text-slate-500">
            <p className="text-sm">
              No FGA checks yet. Send a message on the{' '}
              <Link href="/" className="text-okta-blue underline">
                chat page
              </Link>{' '}
              to see live authorization checks appear here.
            </p>
          </div>
        ) : null}
      </div>
    </main>
  );
}
