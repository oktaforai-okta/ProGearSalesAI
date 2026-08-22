'use client';

import { useState, useRef, useEffect, type ReactNode } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  Bot,
  Fingerprint,
  GitBranch,
  LogOut,
  Network,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { type ApprovalStatus } from '@/components/ApprovalStatusCard';
import { API_BASE_URL, OKTA_DOMAIN } from '@/lib/config';
import { A2AExecutionCard, type A2ATraceEvent } from '@/components/A2AExecutionCard';
import { AgentRegistryPanel } from '@/components/AgentRegistryPanel';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  agentFlow?: any[];
  tokenExchanges?: any[];
  fgaChecks?: any[];
  a2aTrace?: A2ATraceEvent[];
}

// Kept deliberately simple: 2 reads (left column) + 2 writes (right
// column), both about inventory. Earlier versions mixed in
// customer/pricing/margin questions, but those don't exercise the
// read-vs-write security story this demo is actually about, so they were
// dropped per explicit feedback. The two write prompts are picked to
// straddle the OIG approval threshold (500 units) on purpose: 50 auto-
// executes, 600 pauses for human approval -- same mechanism, visibly
// different outcome.
const exampleQuestions: { text: string; action: 'read' | 'write' }[] = [
  { text: "How many Elite Basketballs are in stock?", action: 'read' },
  { text: "We received 50 Elite basketballs. Add them to inventory, refresh Metro Youth League's price, and notify their buyer.", action: 'write' },
];

function isCrossPlatformStory(message: string): boolean {
  const text = message.toLowerCase();
  return ['receive', 'received', 'add', 'increase'].some((word) => text.includes(word))
    && text.includes('basketball')
    && text.includes('metro')
    && ['notify', 'notification', 'buyer'].some((word) => text.includes(word));
}

const CHAT_STORAGE_KEY = 'progear-chat-messages';
const AGENT_FLOW_STORAGE_KEY = 'progear-agent-flow';
const TOKEN_EXCHANGE_STORAGE_KEY = 'progear-token-exchanges';
const FGA_CHECKS_STORAGE_KEY = 'progear-fga-checks';
const PENDING_APPROVAL_STORAGE_KEY = 'progear-pending-approval';
const APPROVAL_ANNOUNCED_STORAGE_KEY = 'progear-approval-announced';

// Pull the router's classified intent (agents + scopes) out of an agent_flow
// array so it can be shown inline under the assistant's reply, even when the
// request later fails for infrastructure reasons. Answers "what did the AI
// understand this prompt to mean" directly, instead of leaving that only
// inferable from whether the answer happened to come back right.
function getRouterSummary(agentFlow?: any[]): string | null {
  if (!agentFlow) return null;
  const routerStep = agentFlow.find((s) => s.step === 'router' && s.agents && s.scopes);
  if (!routerStep) return null;
  const parts = (routerStep.agents as string[]).map((agent) => {
    const scopes = (routerStep.scopes[agent] || []) as string[];
    return `${agent}: ${scopes.join(', ')}`;
  });
  return parts.length ? `Interpreted as → ${parts.join(' · ')}` : null;
}

// Claude's responses come back as markdown (**bold**, numbered lists, etc.)
// which previously rendered as literal asterisks in a plain <p> tag. Map the
// handful of elements actually used in responses to Tailwind-styled tags
// rather than pulling in the @tailwindcss/typography plugin for this alone.
const markdownComponents = {
  p: ({ children }: { children?: ReactNode }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }: { children?: ReactNode }) => <strong className="font-semibold text-white">{children}</strong>,
  ul: ({ children }: { children?: ReactNode }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
  ol: ({ children }: { children?: ReactNode }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
  li: ({ children }: { children?: ReactNode }) => <li>{children}</li>,
  code: ({ children }: { children?: ReactNode }) => (
    <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-sm text-sky-300">{children}</code>
  ),
  // Tables need remark-gfm to even parse (plain react-markdown only speaks
  // CommonMark, not GFM tables) - without it, "| Product | Stock |..." shows
  // up as a literal pipe-delimited line of text instead of a real table.
  table: ({ children }: { children?: ReactNode }) => (
    <div className="overflow-x-auto mb-2">
      <table className="min-w-full rounded-lg border border-white/10 text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => <thead className="bg-white/5">{children}</thead>,
  tr: ({ children }: { children?: ReactNode }) => <tr className="border-b border-white/10 last:border-0">{children}</tr>,
  th: ({ children }: { children?: ReactNode }) => (
    <th className="border-r border-white/10 px-3 py-2 text-left font-semibold text-slate-200 last:border-0">{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="border-r border-white/10 px-3 py-2 last:border-0">{children}</td>
  ),
};

export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [message, setMessage] = useState('');
  const [chatMessages, setChatMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentAgentFlow, setCurrentAgentFlow] = useState<any[]>([]);
  const [currentTokenExchanges, setCurrentTokenExchanges] = useState<any[]>([]);
  const [currentFGAChecks, setCurrentFGAChecks] = useState<any[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalStatus | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isLoadingAuth = status === 'loading';

  // Load chat history from sessionStorage on mount
  useEffect(() => {
    try {
      const savedMessages = sessionStorage.getItem(CHAT_STORAGE_KEY);
      const savedAgentFlow = sessionStorage.getItem(AGENT_FLOW_STORAGE_KEY);
      const savedTokenExchanges = sessionStorage.getItem(TOKEN_EXCHANGE_STORAGE_KEY);
      const savedFGAChecks = sessionStorage.getItem(FGA_CHECKS_STORAGE_KEY);

      if (savedMessages) {
        setChatMessages(JSON.parse(savedMessages));
      }
      if (savedAgentFlow) {
        setCurrentAgentFlow(JSON.parse(savedAgentFlow));
      }
      if (savedTokenExchanges) {
        setCurrentTokenExchanges(JSON.parse(savedTokenExchanges));
      }
      if (savedFGAChecks) {
        setCurrentFGAChecks(JSON.parse(savedFGAChecks));
      }
      const savedPendingApproval = sessionStorage.getItem(PENDING_APPROVAL_STORAGE_KEY);
      if (savedPendingApproval) {
        try {
          setPendingApproval(JSON.parse(savedPendingApproval) as ApprovalStatus);
        } catch {
          /* ignore malformed saved state */
        }
      }
    } catch (e) {
      console.error('Error loading chat history:', e);
    }
  }, []);

  // Save chat history to sessionStorage whenever it changes
  useEffect(() => {
    if (chatMessages.length > 0) {
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatMessages));
    }
  }, [chatMessages]);

  // Save agent flow, token exchanges, and FGA checks to sessionStorage
  useEffect(() => {
    if (currentAgentFlow.length > 0) {
      sessionStorage.setItem(AGENT_FLOW_STORAGE_KEY, JSON.stringify(currentAgentFlow));
    }
    if (currentTokenExchanges.length > 0) {
      sessionStorage.setItem(TOKEN_EXCHANGE_STORAGE_KEY, JSON.stringify(currentTokenExchanges));
    }
    if (currentFGAChecks.length > 0) {
      sessionStorage.setItem(FGA_CHECKS_STORAGE_KEY, JSON.stringify(currentFGAChecks));
    }
    if (pendingApproval) {
      sessionStorage.setItem(PENDING_APPROVAL_STORAGE_KEY, JSON.stringify(pendingApproval));
    } else {
      sessionStorage.removeItem(PENDING_APPROVAL_STORAGE_KEY);
    }
  }, [currentAgentFlow, currentTokenExchanges, currentFGAChecks, pendingApproval]);

  // Debug hook: ?mockApprovalId= populates the ApprovalStatusCard for manual UI testing
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (process.env.NEXT_PUBLIC_ENABLE_DEBUG_HOOKS !== 'true') return;
    const params = new URLSearchParams(window.location.search);
    const mockId = params.get('mockApprovalId');
    if (!mockId) return;
    setPendingApproval({
      request_id: mockId,
      status: 'pending',
      submitted_at: new Date().toISOString(),
      approver_group: 'InventoryApprovers',
      intent: {
        product_name: 'basketball',
        quantity_delta: 500,
        scope: 'inventory:write',
        original_task: 'debug: add 500 basketballs',
      },
    });
  }, []);

  // Redirect to sign-in page if not authenticated
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth/signin');
    }
  }, [status, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleGoHome = () => {
    // Clear chat messages and reset to landing page with prompts
    setChatMessages([]);
    setCurrentAgentFlow([]);
    setCurrentTokenExchanges([]);
    setCurrentFGAChecks([]);
    setPendingApproval(null);
    setMessage('');
    // Clear session storage
    sessionStorage.removeItem(CHAT_STORAGE_KEY);
    sessionStorage.removeItem(AGENT_FLOW_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_EXCHANGE_STORAGE_KEY);
    sessionStorage.removeItem(FGA_CHECKS_STORAGE_KEY);
    sessionStorage.removeItem(PENDING_APPROVAL_STORAGE_KEY);
    sessionStorage.removeItem(APPROVAL_ANNOUNCED_STORAGE_KEY);
  };

  const handleApprovalStatusChange = (latest: ApprovalStatus) => {
    setPendingApproval(latest);
    if (latest.status !== 'executed') return;

    let announced: string[] = [];
    try {
      announced = JSON.parse(sessionStorage.getItem(APPROVAL_ANNOUNCED_STORAGE_KEY) || '[]');
    } catch {
      announced = [];
    }
    if (announced.includes(latest.request_id)) return;
    announced.push(latest.request_id);
    sessionStorage.setItem(APPROVAL_ANNOUNCED_STORAGE_KEY, JSON.stringify(announced));

    const intent = latest.intent ?? {};
    const er = latest.execution_result;
    const approverSuffix = latest.approver?.display_name
      ? ` by ${latest.approver.display_name}`
      : latest.approver?.email
        ? ` by ${latest.approver.email}`
        : '';
    const product = intent.product_name ?? 'item';
    const qty =
      typeof intent.quantity_delta === 'number'
        ? `+${intent.quantity_delta.toLocaleString()}`
        : '';
    const inventoryLine =
      er && er.previous_quantity >= 0 && er.new_quantity >= 0
        ? `Inventory for ${product}: ${er.previous_quantity.toLocaleString()} → ${er.new_quantity.toLocaleString()}${qty ? ` (${qty})` : ''}.`
        : '';
    const txnLine = er?.txn_id ? `Transaction: ${er.txn_id}` : '';

    const body = [
      `Your previous request ${latest.request_id} was approved${approverSuffix} and has been executed.`,
      inventoryLine,
      txnLine,
    ]
      .filter(Boolean)
      .join('\n');

    setChatMessages((prev) => [
      ...prev,
      {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: body,
        timestamp: Date.now(),
      },
    ]);
  };

  // Now that the Token/Approval detail card lives on /tokens, the chat page
  // owns its own lightweight poll so a pending manager-approval request still
  // gets announced in the conversation even if the user never opens /tokens.
  useEffect(() => {
    if (!pendingApproval) return;
    if (pendingApproval.status === 'executed' || pendingApproval.status === 'denied') return;

    let cancelled = false;
    const baseDelay = 15_000;
    const maxDelay = 120_000;
    let delay = baseDelay;
    let handle: ReturnType<typeof setTimeout> | undefined;

    const schedule = () => {
      if (!cancelled) handle = setTimeout(tick, delay);
    };

    const tick = async () => {
      try {
        const idToken = session?.idToken;
        if (!idToken) return;
        const res = await fetch(`${API_BASE_URL}/api/approvals/${pendingApproval.request_id}`, {
          headers: { Authorization: `Bearer ${idToken}` },
        });
        if (res.status === 429) {
          const retryAfter = Number(res.headers.get('Retry-After') || 0) * 1000;
          delay = Math.min(maxDelay, Math.max(retryAfter, delay * 2));
          return;
        }
        if (!res.ok || cancelled) {
          delay = Math.min(maxDelay, delay * 2);
          return;
        }
        const data: ApprovalStatus = await res.json();
        delay = baseDelay;
        if (!cancelled) {
          handleApprovalStatusChange(data);
          if (data.status === 'executed' || data.status === 'denied') {
            cancelled = true;
          }
        }
      } catch {
        delay = Math.min(maxDelay, delay * 2);
      } finally {
        schedule();
      }
    };

    schedule();
    return () => {
      cancelled = true;
      if (handle) clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingApproval?.request_id, pendingApproval?.status, session?.idToken]);

  const handleSignOut = async () => {
    // Get the idToken BEFORE signing out (session will be cleared after signOut)
    const idToken = session?.idToken;

    // Clear the NextAuth session
    await signOut({ redirect: false });

    // Clear chat history on sign out
    sessionStorage.removeItem(CHAT_STORAGE_KEY);
    sessionStorage.removeItem(AGENT_FLOW_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_EXCHANGE_STORAGE_KEY);
    sessionStorage.removeItem(FGA_CHECKS_STORAGE_KEY);
    sessionStorage.removeItem(PENDING_APPROVAL_STORAGE_KEY);

    // End Okta session using OIDC logout endpoint
    // Reference: https://developer.okta.com/docs/guides/sign-users-out/react/main/
    const oktaDomain = OKTA_DOMAIN;
    const postLogoutRedirect = encodeURIComponent(`${window.location.origin}/auth/signin`);

    if (oktaDomain && idToken) {
      // OIDC logout endpoint with id_token_hint
      window.location.href = `${oktaDomain}/oauth2/v1/logout?id_token_hint=${idToken}&post_logout_redirect_uri=${postLogoutRedirect}`;
    } else if (oktaDomain) {
      // Fallback without id_token
      window.location.href = `${oktaDomain}/oauth2/v1/logout?post_logout_redirect_uri=${postLogoutRedirect}`;
    } else {
      window.location.href = '/auth/signin';
    }
  };

  const handleSendMessage = async (text?: string) => {
    const userMessage = text || message.trim();
    if (!userMessage) return;

    setMessage('');
    const newUserMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: userMessage,
      timestamp: Date.now(),
    };
    setChatMessages((prev) => [...prev, newUserMessage]);
    setIsLoading(true);
    setCurrentAgentFlow([{ step: 'router', action: 'Processing request...', status: 'processing' }]);
    setCurrentTokenExchanges([]);
    setCurrentFGAChecks([]);

    try {
      const idToken = session?.idToken;
      const a2aRequest = isCrossPlatformStory(userMessage);

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (!a2aRequest && idToken) {
        headers['Authorization'] = `Bearer ${idToken}`;
      }

      if (a2aRequest) {
        if (!session?.accessToken) {
          throw new Error('Your session has no coordinator access token. Please sign in again.');
        }
        headers['Authorization'] = `Bearer ${session.accessToken}`;
      }

      const response = await fetch(`${API_BASE_URL}${a2aRequest ? '/api/a2a/execute' : '/api/chat'}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: userMessage }),
      });

      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json')
        ? await response.json()
        : { content: await response.text() };

      // Preserve any evidence the backend returned, including denied and
      // system-error exchange records.
      setCurrentAgentFlow(data.agent_flow || data.events || []);
      setCurrentTokenExchanges(a2aRequest ? [] : data.token_exchanges || []);
      setCurrentFGAChecks(a2aRequest ? [] : data.fga_checks || []);
      if (data.pending_approval) {
        setPendingApproval(data.pending_approval);
      }

      if (!response.ok) {
        const detail = data.detail || data.content;
        throw new Error(
          typeof detail === 'string' && detail.trim()
            ? detail
            : `Backend request failed with HTTP ${response.status}`
        );
      }

      const assistantMessage: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: data.content,
        timestamp: Date.now(),
        agentFlow: data.agent_flow,
        tokenExchanges: data.token_exchanges,
        fgaChecks: data.fga_checks,
        a2aTrace: data.events,
      };
      setChatMessages((prev) => [...prev, assistantMessage]);

    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = error instanceof Error ? error.message : '';
      setChatMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: errorMessage
            ? `The request could not reach the ProGear service. ${errorMessage}`
            : 'The request could not reach the ProGear service. Please try again.',
          timestamp: Date.now(),
        },
      ]);
      setCurrentAgentFlow([{ step: 'error', action: 'Request failed', status: 'error' }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Show loading screen while checking auth status
  if (isLoadingAuth || status === 'unauthenticated') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#080c12]">
        <div className="flex flex-col items-center gap-4">
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-2xl">
            🏀
            <span className="absolute -right-1 -top-1 h-3 w-3 animate-pulse rounded-full border-2 border-[#080c12] bg-emerald-400" />
          </div>
          <div className="text-xs font-medium uppercase tracking-[0.25em] text-slate-500">Opening ProGear workspace</div>
        </div>
      </div>
    );
  }

  return (
    <main className="relative flex h-screen flex-col overflow-hidden bg-[#080c12] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_12%_0%,rgba(56,189,248,0.09),transparent_30%),radial-gradient(circle_at_88%_8%,rgba(139,92,246,0.08),transparent_27%)]" />

      <header className="relative z-20 border-b border-white/10 bg-[#0b1018]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1500px] items-center justify-between gap-4 px-4 sm:px-6">
          <button onClick={handleGoHome} className="flex items-center gap-3 text-left" title="Start a new conversation">
            <span className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-orange-400/20 bg-orange-400/10 text-lg">
              🏀
              <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#0b1018] bg-emerald-400" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-tight text-white">CourtEdge ProGear</span>
              <span className="block text-[10px] text-slate-500">Governed sales operations</span>
            </span>
          </button>

          <nav className="hidden items-center gap-1 rounded-xl border border-white/[0.08] bg-white/[0.025] p-1 md:flex">
            <button onClick={handleGoHome} className="rounded-lg bg-white/[0.06] px-3 py-1.5 text-[11px] font-medium text-white">Workspace</button>
            <Link href="/tokens" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/[0.05] hover:text-white"><Fingerprint className="h-3.5 w-3.5" />Delegation evidence</Link>
            <Link href="/architecture" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/[0.05] hover:text-white"><GitBranch className="h-3.5 w-3.5" />Architecture</Link>
          </nav>

          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.025] px-2.5 py-1.5 sm:flex">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-sky-400/10 text-sky-300"><UserRound className="h-3.5 w-3.5" /></span>
              <div className="max-w-[170px]">
                <p className="truncate text-[10px] font-medium text-slate-200">{session?.user?.name || session?.user?.email}</p>
                <p className="text-[9px] text-emerald-400">Password-authenticated</p>
              </div>
            </div>
            <button onClick={handleSignOut} className="rounded-lg border border-white/[0.08] p-2 text-slate-500 hover:border-white/20 hover:text-white" title="Sign out"><LogOut className="h-4 w-4" /></button>
          </div>
        </div>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1">
        <div className="flex w-full flex-col">
          <div className="mx-auto w-full max-w-6xl flex-1 space-y-5 overflow-y-auto px-5 py-6 sm:px-8">
            {chatMessages.length === 0 && (
              <div className="py-4">
                <div className="grid items-stretch gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.65fr)]">
                  <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.055] to-white/[0.02] p-6 sm:p-8">
                    <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/[0.08] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-300">
                      <Sparkles className="h-3 w-3" /> Cross-platform agent mesh
                    </div>
                    <h2 className="mt-5 max-w-2xl text-3xl font-semibold leading-tight tracking-[-0.035em] text-white sm:text-4xl">
                      One request. Two clouds. One verifiable custody trail.
                    </h2>
                    <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-400">
                      Receive inventory in AWS, refresh a customer price, and notify through Google—while Okta preserves who authorized every hop and the Bridge isolates each MCP resource.
                    </p>

                    <div className="mt-7 grid gap-3 sm:grid-cols-2">
                      {exampleQuestions.map((question, idx) => {
                        const isWrite = question.action === 'write';
                        return (
                          <button key={idx} onClick={() => handleSendMessage(question.text)} className="group rounded-xl border border-white/10 bg-black/20 p-4 text-left hover:border-sky-400/30 hover:bg-sky-400/[0.04]">
                            <span className={`inline-flex rounded-md px-2 py-1 text-[9px] font-semibold uppercase tracking-wider ${isWrite ? 'bg-orange-400/10 text-orange-300' : 'bg-emerald-400/10 text-emerald-300'}`}>{isWrite ? 'Cross-cloud write' : 'Inventory read'}</span>
                            <span className="mt-3 flex items-start justify-between gap-3 text-xs font-medium leading-relaxed text-slate-200">
                              {question.text}<ArrowRight className="mt-0.5 h-4 w-4 flex-none text-slate-600 transition-transform group-hover:translate-x-0.5 group-hover:text-sky-300" />
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section className="rounded-2xl border border-white/10 bg-[#0b1018] p-5 sm:p-6">
                    <div className="flex items-center justify-between">
                      <h3 className="flex items-center gap-2 text-xs font-semibold text-white"><Network className="h-4 w-4 text-violet-300" />The story, in order</h3>
                      <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-emerald-300">Live mesh</span>
                    </div>
                    <ol className="mt-5 space-y-4">
                      {[
                        ['01', 'Human signs in', 'Sarah Sales or Mike Manager establishes the root authority.'],
                        ['02', 'Google reads context', 'The Customer Agent checks tier, channel, and consent through its MCP resource.'],
                        ['03', 'AWS commits inventory', 'AgentCore writes stock and returns an authoritative price receipt.'],
                        ['04', 'Google notifies', 'Notification is accepted only when bound to the AWS receipt.'],
                      ].map(([number, title, copy]) => (
                        <li key={number} className="flex gap-3">
                          <span className="font-mono text-[10px] text-sky-400">{number}</span>
                          <div><p className="text-[11px] font-medium text-slate-200">{title}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-500">{copy}</p></div>
                        </li>
                      ))}
                    </ol>
                    <div className="mt-5 border-t border-white/10 pt-4 text-[10px] leading-relaxed text-slate-500">
                      <ShieldCheck className="mr-1.5 inline h-3.5 w-3.5 text-emerald-300" />Separate target tokens. Nested actor evidence. No raw credentials in the UI.
                    </div>
                  </section>
                </div>

                <div className="mt-5"><AgentRegistryPanel /></div>
              </div>
            )}

            {chatMessages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex w-full items-start gap-3 ${msg.role === 'user' ? 'max-w-2xl flex-row-reverse' : 'max-w-5xl'}`}>
                  <div className={`flex h-9 w-9 flex-none items-center justify-center rounded-xl border ${msg.role === 'user' ? 'border-orange-400/20 bg-orange-400/10 text-orange-300' : 'border-sky-400/20 bg-sky-400/10 text-sky-300'}`}>
                    {msg.role === 'user' ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>

                  <div className={`min-w-0 rounded-2xl border p-4 sm:p-5 ${msg.role === 'user' ? 'border-orange-400/15 bg-orange-400/[0.08] text-slate-100' : 'w-full border-white/10 bg-white/[0.035]'}`}>
                    {msg.role === 'assistant' ? (
                      <div className="text-sm leading-relaxed text-slate-300 [&_p:last-child]:mb-0">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
                    )}
                    {msg.role === 'assistant' && getRouterSummary(msg.agentFlow) && (
                      <div className="mt-3 border-t border-white/10 pt-3 font-mono text-[10px] text-sky-400/80">
                        {getRouterSummary(msg.agentFlow)}
                      </div>
                    )}
                    {msg.role === 'assistant' && <A2AExecutionCard events={msg.a2aTrace} subject={session?.user?.name || session?.user?.email} />}
                    <div className="mt-2 text-[9px] uppercase tracking-wider text-slate-600">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 flex-none items-center justify-center rounded-xl border border-sky-400/20 bg-sky-400/10 text-sky-300"><Bot className="h-4 w-4" /></div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1.5">
                        <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-300" style={{ animationDelay: '0ms' }} />
                        <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-violet-300" style={{ animationDelay: '150ms' }} />
                        <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-emerald-300" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-xs text-slate-500">Coordinating governed AWS and Google agents…</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-white/10 bg-[#0b1018]/95 px-5 py-4 backdrop-blur-xl sm:px-8">
            <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="mx-auto flex max-w-5xl gap-3">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Ask ProGear to receive inventory, refresh Metro pricing, and notify the buyer..."
                  className="w-full rounded-xl border border-white/10 bg-white/[0.045] px-4 py-3 pr-12 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-sky-400/40 focus:ring-2 focus:ring-sky-400/10"
                  disabled={isLoading}
                />
                <ShieldCheck className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-emerald-400/50" />
              </div>
              <button
                type="submit"
                disabled={isLoading || !message.trim()}
                className="inline-flex items-center gap-2 rounded-xl bg-sky-400 px-5 py-3 text-xs font-semibold text-slate-950 shadow-lg shadow-sky-400/10 hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Send className="h-4 w-4" /><span className="hidden sm:inline">Send</span>
              </button>
            </form>
            <p className="mx-auto mt-2 max-w-5xl text-center text-[9px] text-slate-600">Authority is evaluated per target. Credentials are never sent to the model or displayed in this workspace.</p>
          </div>
        </div>
      </div>
    </main>
  );
}
