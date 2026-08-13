'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { ArrowLeft } from 'lucide-react';
import RawTokensCard from '@/components/RawTokensCard';
import ApprovalStatusCard, { type ApprovalStatus } from '@/components/ApprovalStatusCard';

const AGENT_FLOW_STORAGE_KEY = 'progear-agent-flow';
const TOKEN_EXCHANGE_STORAGE_KEY = 'progear-token-exchanges';
const PENDING_APPROVAL_STORAGE_KEY = 'progear-pending-approval';

// Reads the exact same sessionStorage the chat page (/) already writes on
// every response - no backend or API changes needed to power this page.
export default function TokensPage() {
  const { data: session } = useSession();
  const [agentFlow, setAgentFlow] = useState<any[]>([]);
  const [tokenExchanges, setTokenExchanges] = useState<any[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalStatus | null>(null);

  const loadFromStorage = () => {
    try {
      const flow = sessionStorage.getItem(AGENT_FLOW_STORAGE_KEY);
      const exchanges = sessionStorage.getItem(TOKEN_EXCHANGE_STORAGE_KEY);
      const approval = sessionStorage.getItem(PENDING_APPROVAL_STORAGE_KEY);
      if (flow) setAgentFlow(JSON.parse(flow));
      if (exchanges) setTokenExchanges(JSON.parse(exchanges));
      if (approval) setPendingApproval(JSON.parse(approval));
    } catch (e) {
      console.error('Error loading token data:', e);
    }
  };

  useEffect(() => {
    loadFromStorage();
    // Picks up new data if the user sends another message from the chat tab
    // while this page is also open.
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
              <h1 className="text-white text-xl font-bold">Token Flow</h1>
              <p className="text-gray-300 text-xs">Agent flow and the raw token exchange chain</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <RawTokensCard
          exchanges={tokenExchanges}
          idTokenRaw={session?.idToken}
        />

        {pendingApproval && (
          <ApprovalStatusCard key={pendingApproval.request_id} initial={pendingApproval} />
        )}

        {agentFlow.length === 0 && tokenExchanges.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-sm">
              No activity yet. Send a message on the{' '}
              <Link href="/" className="text-okta-blue underline">
                chat page
              </Link>{' '}
              to see token exchanges appear here.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
