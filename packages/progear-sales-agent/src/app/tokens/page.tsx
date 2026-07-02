'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { ArrowLeft } from 'lucide-react';
import AgentFlowCard from '@/components/AgentFlowCard';
import TokenExchangeCard from '@/components/TokenExchangeCard';
import RawTokensCard from '@/components/RawTokensCard';
import FGAExplanationCard from '@/components/FGAExplanationCard';
import ApprovalStatusCard, { type ApprovalStatus } from '@/components/ApprovalStatusCard';
import FGAControlsPanel from '@/components/FGAControlsPanel';

const AGENT_FLOW_STORAGE_KEY = 'progear-agent-flow';
const TOKEN_EXCHANGE_STORAGE_KEY = 'progear-token-exchanges';
const FGA_CHECKS_STORAGE_KEY = 'progear-fga-checks';
const PENDING_APPROVAL_STORAGE_KEY = 'progear-pending-approval';

// Decode JWT payload (for display only, no validation)
function decodeJwtPayload(token: string): Record<string, any> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const decoded = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

// Reads the exact same sessionStorage the chat page (/) already writes on
// every response - no backend or API changes needed to power this page.
export default function TokensPage() {
  const { data: session } = useSession();
  const [agentFlow, setAgentFlow] = useState<any[]>([]);
  const [tokenExchanges, setTokenExchanges] = useState<any[]>([]);
  const [fgaChecks, setFgaChecks] = useState<any[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalStatus | null>(null);

  const loadFromStorage = () => {
    try {
      const flow = sessionStorage.getItem(AGENT_FLOW_STORAGE_KEY);
      const exchanges = sessionStorage.getItem(TOKEN_EXCHANGE_STORAGE_KEY);
      const checks = sessionStorage.getItem(FGA_CHECKS_STORAGE_KEY);
      const approval = sessionStorage.getItem(PENDING_APPROVAL_STORAGE_KEY);
      if (flow) setAgentFlow(JSON.parse(flow));
      if (exchanges) setTokenExchanges(JSON.parse(exchanges));
      if (checks) setFgaChecks(JSON.parse(checks));
      if (approval) setPendingApproval(JSON.parse(approval));
    } catch (e) {
      console.error('Error loading token/FGA data:', e);
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
              <h1 className="text-white text-xl font-bold">Tokens &amp; Governance</h1>
              <p className="text-gray-300 text-xs">Agent flow, token exchanges, and Fine-Grained Authorization</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <AgentFlowCard steps={agentFlow} />

        <TokenExchangeCard exchanges={tokenExchanges} />

        <RawTokensCard
          exchanges={tokenExchanges}
          idTokenClaims={session?.idToken ? decodeJwtPayload(session.idToken) ?? undefined : undefined}
          idTokenRaw={session?.idToken}
        />

        <FGAExplanationCard checks={fgaChecks} />

        <FGAControlsPanel onApplied={loadFromStorage} />

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
              to see token exchanges and FGA checks appear here.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
