'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import FGAExplanationCard from '@/components/FGAExplanationCard';
import FGAControlsPanel from '@/components/FGAControlsPanel';

const FGA_CHECKS_STORAGE_KEY = 'progear-fga-checks';

// Reads the exact same sessionStorage the chat page (/) already writes on
// every response - no backend or API changes needed to power this page.
export default function FGAPage() {
  const [fgaChecks, setFgaChecks] = useState<any[]>([]);

  const loadFromStorage = () => {
    try {
      const checks = sessionStorage.getItem(FGA_CHECKS_STORAGE_KEY);
      if (checks) setFgaChecks(JSON.parse(checks));
    } catch (e) {
      console.error('Error loading fine-grained control data:', e);
    }
  };

  useEffect(() => {
    loadFromStorage();
    const onFocus = () => loadFromStorage();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
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
              <h1 className="text-white text-xl font-bold">Fine-Grained Controls</h1>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <FGAExplanationCard checks={fgaChecks} />

        <FGAControlsPanel onApplied={loadFromStorage} />

        {fgaChecks.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-sm">
              No fine-grained checks yet. Send a message on the{' '}
              <Link href="/" className="text-okta-blue underline">
                chat page
              </Link>{' '}
              to see live authorization checks appear here.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
