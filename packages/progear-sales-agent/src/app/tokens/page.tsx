'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import {
  ArrowLeft,
  CheckCircle2,
  CloudCog,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react';
import ApprovalStatusCard, { type ApprovalStatus } from '@/components/ApprovalStatusCard';
import { ChainOfCustody, type A2ATraceEvent } from '@/components/ChainOfCustody';

const AGENT_FLOW_STORAGE_KEY = 'progear-agent-flow';
const TOKEN_EXCHANGE_STORAGE_KEY = 'progear-token-exchanges';
const PENDING_APPROVAL_STORAGE_KEY = 'progear-pending-approval';

interface LegacyExchange {
  agent_name?: string;
  agent?: string;
  success?: boolean;
  access_denied?: boolean;
  status?: string;
  scopes?: string[];
}

export default function TokensPage() {
  const { data: session } = useSession();
  const [agentFlow, setAgentFlow] = useState<A2ATraceEvent[]>([]);
  const [tokenExchanges, setTokenExchanges] = useState<LegacyExchange[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalStatus | null>(null);

  const loadFromStorage = () => {
    try {
      const flow = sessionStorage.getItem(AGENT_FLOW_STORAGE_KEY);
      const exchanges = sessionStorage.getItem(TOKEN_EXCHANGE_STORAGE_KEY);
      const approval = sessionStorage.getItem(PENDING_APPROVAL_STORAGE_KEY);
      if (flow) setAgentFlow(JSON.parse(flow));
      if (exchanges) setTokenExchanges(JSON.parse(exchanges));
      if (approval) setPendingApproval(JSON.parse(approval));
    } catch (error) {
      console.error('Error loading delegation evidence:', error);
    }
  };

  useEffect(() => {
    loadFromStorage();
    window.addEventListener('focus', loadFromStorage);
    return () => window.removeEventListener('focus', loadFromStorage);
  }, []);

  const a2aEvents = useMemo(
    () => agentFlow.filter((event) => event?.correlation_id && event?.platform && event?.agent),
    [agentFlow],
  );
  const completed = a2aEvents.filter((event) => event.status === 'completed').length;
  const correlationId = a2aEvents.find((event) => event.correlation_id)?.correlation_id;
  const subject = session?.user?.name || session?.user?.email || 'Signed-in user';

  return (
    <main className="min-h-screen bg-[#080c12] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_15%_0%,rgba(56,189,248,0.10),transparent_34%),radial-gradient(circle_at_85%_12%,rgba(139,92,246,0.10),transparent_30%)]" />

      <header className="relative border-b border-white/10 bg-[#0b1018]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <div className="flex items-center gap-4">
            <Link href="/" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-300 hover:border-sky-400/30 hover:text-white">
              <ArrowLeft className="h-4 w-4" /> Back to workspace
            </Link>
            <div className="hidden h-8 w-px bg-white/10 sm:block" />
            <div>
              <div className="flex items-center gap-2">
                <Fingerprint className="h-4 w-4 text-sky-300" />
                <h1 className="text-sm font-semibold tracking-tight text-white">Delegation evidence</h1>
              </div>
              <p className="mt-0.5 text-[11px] text-slate-500">A safe retrospective of who acted for whom, where, and with what authority</p>
            </div>
          </div>
          <span className="hidden rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-emerald-300 sm:inline-flex">
            Credential-safe view
          </span>
        </div>
      </header>

      <div className="relative mx-auto max-w-7xl px-5 py-7 sm:px-8">
        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500"><ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />Verified stages</div>
            <p className="mt-2 text-2xl font-semibold text-white">{completed || '—'}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">Completed within the current business run</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500"><CloudCog className="h-3.5 w-3.5 text-violet-300" />Builder platforms</div>
            <p className="mt-2 text-sm font-semibold text-white">Google ADK + AWS AgentCore</p>
            <p className="mt-1 text-[11px] text-slate-500">One governed workflow across two runtimes</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500"><KeyRound className="h-3.5 w-3.5 text-sky-300" />Correlation</div>
            <p className="mt-2 truncate font-mono text-sm font-semibold text-white">{correlationId || 'No run captured'}</p>
            <p className="mt-1 text-[11px] text-slate-500">Connects delegation, resource calls, and receipts</p>
          </div>
        </div>

        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_310px]">
          <div className="space-y-5">
            {a2aEvents.length > 0 ? (
              <ChainOfCustody events={a2aEvents} subject={subject} />
            ) : (
              <section className="rounded-2xl border border-dashed border-white/15 bg-white/[0.025] px-6 py-16 text-center">
                <Fingerprint className="mx-auto h-8 w-8 text-slate-700" />
                <h2 className="mt-4 text-sm font-semibold text-slate-300">No cross-platform run captured yet</h2>
                <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-slate-500">
                  Run the receive, reprice, and notify example from the workspace. Its safe delegation evidence will appear here—without exposing the credentials themselves.
                </p>
                <Link href="/" className="mt-5 inline-flex rounded-lg bg-sky-400 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-300">Run the story</Link>
              </section>
            )}

            {tokenExchanges.length > 0 && a2aEvents.length === 0 && (
              <section className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
                <h2 className="text-xs font-semibold text-white">Earlier specialist decisions</h2>
                <p className="mt-1 text-[11px] text-slate-500">Only outcome and scope metadata is shown. Encoded tokens and identity identifiers are omitted.</p>
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  {tokenExchanges.map((exchange, index) => (
                    <div key={`${exchange.agent || exchange.agent_name || 'agent'}-${index}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-200">{exchange.agent_name || exchange.agent || 'Specialist agent'}</span>
                        <span className={`text-[9px] font-semibold uppercase tracking-wider ${exchange.success ? 'text-emerald-300' : 'text-amber-300'}`}>{exchange.success ? 'Granted' : exchange.access_denied ? 'Denied' : 'Stopped'}</span>
                      </div>
                      <p className="mt-2 font-mono text-[10px] text-sky-300">{exchange.scopes?.join(' · ') || 'No scope granted'}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {pendingApproval && <ApprovalStatusCard key={pendingApproval.request_id} initial={pendingApproval} />}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-5">
            <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
              <h2 className="flex items-center gap-2 text-xs font-semibold text-white"><CheckCircle2 className="h-4 w-4 text-emerald-300" />What this proves</h2>
              <ol className="mt-4 space-y-4">
                {[
                  ['1', 'Human authority persists', `${subject} remains the subject while agents become nested actors.`],
                  ['2', 'Each audience is isolated', 'Google and AWS receive separate target-bound authority; scopes are never unioned.'],
                  ['3', 'The receipt controls order', 'Google can notify only after AWS returns an authoritative, correlation-bound inventory receipt.'],
                  ['4', 'Resources stay segmented', 'Each specialist reaches only its linked MCP resource through the Bridge.'],
                ].map(([number, title, copy]) => (
                  <li key={number} className="flex gap-3">
                    <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-sky-400/10 text-[10px] font-semibold text-sky-300">{number}</span>
                    <div><p className="text-[11px] font-medium text-slate-200">{title}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-500">{copy}</p></div>
                  </li>
                ))}
              </ol>
            </section>

            <section className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-5">
              <h2 className="flex items-center gap-2 text-xs font-semibold text-emerald-200"><LockKeyhole className="h-4 w-4" />Deliberately not displayed</h2>
              <p className="mt-2 text-[10px] leading-relaxed text-slate-500">Raw JWTs, tenant IDs, workload principal IDs, client assertions, private keys, and bearer values never enter this view.</p>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
