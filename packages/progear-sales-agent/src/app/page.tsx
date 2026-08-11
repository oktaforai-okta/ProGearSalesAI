'use client';

import { useState, useRef, useEffect, type ReactNode } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Key, GitBranch, ShieldCheck } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { type ApprovalStatus } from '@/components/ApprovalStatusCard';
import { ThemeSelector } from '@/components/ThemeProvider';
import { API_BASE_URL, OKTA_DOMAIN } from '@/lib/config';
import { useFGASimulation } from '@/hooks/useFGASimulation';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  agentFlow?: any[];
  tokenExchanges?: any[];
  fgaChecks?: any[];
  authorizationDecisions?: any[];
}

type ExampleQuestion = {
  text: string;
  badge: string;
  action: 'read' | 'standard' | 'large';
};

// The everyday demo stays focused on the two core personas. The advanced FGA
// demo adds the quantity boundary without duplicating the Manager tier.
const simpleExampleQuestions: ExampleQuestion[] = [
  { text: 'How many basketballs are in stock?', badge: 'Read', action: 'read' },
  { text: 'Can you add 50 basketballs to the inventory?', badge: 'Write', action: 'standard' },
];

const fgaExampleQuestions: ExampleQuestion[] = [
  { text: 'How many basketballs are in stock?', badge: 'Read', action: 'read' },
  { text: 'Add 50 basketballs to inventory', badge: '1–600', action: 'standard' },
  { text: 'Add 601 basketballs to inventory', badge: '601+ · VP', action: 'large' },
];

const CHAT_STORAGE_KEY = 'progear-chat-messages';
const AGENT_FLOW_STORAGE_KEY = 'progear-agent-flow';
const TOKEN_EXCHANGE_STORAGE_KEY = 'progear-token-exchanges';
const FGA_CHECKS_STORAGE_KEY = 'progear-fga-checks';
const AUTHORIZATION_DECISIONS_STORAGE_KEY = 'progear-authorization-decisions';
const TOKEN_FLOW_STOP_STORAGE_KEY = 'progear-token-flow-stop';
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
  strong: ({ children }: { children?: ReactNode }) => <strong className="font-semibold text-gray-900">{children}</strong>,
  ul: ({ children }: { children?: ReactNode }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
  ol: ({ children }: { children?: ReactNode }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
  li: ({ children }: { children?: ReactNode }) => <li>{children}</li>,
  code: ({ children }: { children?: ReactNode }) => (
    <code className="bg-gray-100 text-accent px-1 py-0.5 rounded text-sm font-mono">{children}</code>
  ),
  // Tables need remark-gfm to even parse (plain react-markdown only speaks
  // CommonMark, not GFM tables) - without it, "| Product | Stock |..." shows
  // up as a literal pipe-delimited line of text instead of a real table.
  table: ({ children }: { children?: ReactNode }) => (
    <div className="overflow-x-auto mb-2">
      <table className="min-w-full border border-neutral-border rounded-lg text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => <thead className="bg-gray-50">{children}</thead>,
  tr: ({ children }: { children?: ReactNode }) => <tr className="border-b border-neutral-border last:border-0">{children}</tr>,
  th: ({ children }: { children?: ReactNode }) => (
    <th className="px-3 py-2 text-left font-semibold text-gray-700 border-r border-neutral-border last:border-0">{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="px-3 py-2 border-r border-neutral-border last:border-0">{children}</td>
  ),
};

export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const { isEnabled: isFGASimulationEnabled } = useFGASimulation();
  const [message, setMessage] = useState('');
  const [chatMessages, setChatMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentAgentFlow, setCurrentAgentFlow] = useState<any[]>([]);
  const [currentTokenExchanges, setCurrentTokenExchanges] = useState<any[]>([]);
  const [currentFGAChecks, setCurrentFGAChecks] = useState<any[]>([]);
  const [currentAuthorizationDecisions, setCurrentAuthorizationDecisions] = useState<any[]>([]);
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
      const savedAuthorizationDecisions = sessionStorage.getItem(AUTHORIZATION_DECISIONS_STORAGE_KEY);

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
      if (savedAuthorizationDecisions) {
        setCurrentAuthorizationDecisions(JSON.parse(savedAuthorizationDecisions));
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
    if (currentAuthorizationDecisions.length > 0) {
      sessionStorage.setItem(AUTHORIZATION_DECISIONS_STORAGE_KEY, JSON.stringify(currentAuthorizationDecisions));
    }
    if (pendingApproval) {
      sessionStorage.setItem(PENDING_APPROVAL_STORAGE_KEY, JSON.stringify(pendingApproval));
    } else {
      sessionStorage.removeItem(PENDING_APPROVAL_STORAGE_KEY);
    }
  }, [currentAgentFlow, currentTokenExchanges, currentFGAChecks, currentAuthorizationDecisions, pendingApproval]);

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
    setCurrentAuthorizationDecisions([]);
    setPendingApproval(null);
    setMessage('');
    // Clear session storage
    sessionStorage.removeItem(CHAT_STORAGE_KEY);
    sessionStorage.removeItem(AGENT_FLOW_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_EXCHANGE_STORAGE_KEY);
    sessionStorage.removeItem(FGA_CHECKS_STORAGE_KEY);
    sessionStorage.removeItem(AUTHORIZATION_DECISIONS_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_FLOW_STOP_STORAGE_KEY);
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
    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/approvals/${pendingApproval.request_id}`);
        if (!res.ok || cancelled) return;
        const data: ApprovalStatus = await res.json();
        if (!cancelled) handleApprovalStatusChange(data);
      } catch {
        /* next tick retries */
      }
    };

    tick();
    const handle = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingApproval?.request_id, pendingApproval?.status]);

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
    sessionStorage.removeItem(AUTHORIZATION_DECISIONS_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_FLOW_STOP_STORAGE_KEY);
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
    setCurrentAuthorizationDecisions([]);
    setPendingApproval(null);
    sessionStorage.removeItem(AGENT_FLOW_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_EXCHANGE_STORAGE_KEY);
    sessionStorage.removeItem(FGA_CHECKS_STORAGE_KEY);
    sessionStorage.removeItem(AUTHORIZATION_DECISIONS_STORAGE_KEY);
    sessionStorage.removeItem(PENDING_APPROVAL_STORAGE_KEY);
    sessionStorage.removeItem(TOKEN_FLOW_STOP_STORAGE_KEY);

    let responseStatus: number | null = null;

    try {
      const idToken = session?.idToken;

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (idToken) {
        headers['Authorization'] = `Bearer ${idToken}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: userMessage,
          simulate_fga: isFGASimulationEnabled,
        }),
      });
      responseStatus = response.status;

      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json')
        ? await response.json()
        : { content: await response.text() };

      // Preserve any evidence the backend returned, including denied and
      // system-error exchange records.
      setCurrentAgentFlow(data.agent_flow || []);
      setCurrentTokenExchanges(data.token_exchanges || []);
      setCurrentFGAChecks(data.fga_checks || []);
      setCurrentAuthorizationDecisions(data.authorization_decisions || []);
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

      sessionStorage.removeItem(TOKEN_FLOW_STOP_STORAGE_KEY);

      const assistantMessage: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: data.content,
        timestamp: Date.now(),
        agentFlow: data.agent_flow,
        tokenExchanges: data.token_exchanges,
        fgaChecks: data.fga_checks,
        authorizationDecisions: data.authorization_decisions,
      };
      setChatMessages((prev) => [...prev, assistantMessage]);

    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = error instanceof Error ? error.message : '';
      const stopPrefix = responseStatus === 401
        ? 'Authentication stopped before token exchange.'
        : responseStatus === 503
          ? 'Authorization context could not be verified before token exchange.'
          : 'Request stopped before token exchange.';
      const tokenFlowStop = errorMessage
        ? `${stopPrefix} ${errorMessage}`
        : `${stopPrefix} Please try again.`;
      sessionStorage.setItem(TOKEN_FLOW_STOP_STORAGE_KEY, tokenFlowStop);
      setChatMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: errorMessage || 'The request could not reach the ProGear service. Please try again.',
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
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary via-primary-light to-court-brown">
        <div className="flex flex-col items-center space-y-4">
          <span className="text-6xl animate-bounce">🏀</span>
          <div className="text-white text-xl font-display">Loading CourtEdge ProGear...</div>
        </div>
      </div>
    );
  }

  return (
    <main className="flex h-screen flex-col bg-gradient-to-b from-slate-100 to-white dark:from-neutral-bg dark:to-primary">
      {/* Header */}
      <header className="bg-gradient-to-r from-primary via-court-brown to-primary-light border-b-4 border-accent shadow-lg relative overflow-hidden">
        {/* Court pattern */}
        <div className="absolute inset-0 opacity-5">
          <svg className="w-full h-full" viewBox="0 0 100 30" preserveAspectRatio="none">
            <line x1="50" y1="0" x2="50" y2="30" stroke="#ff6b35" strokeWidth="0.5"/>
            <circle cx="50" cy="15" r="8" fill="none" stroke="#ff6b35" strokeWidth="0.3"/>
          </svg>
        </div>

        <div className="px-6 py-4 flex justify-between items-center relative z-10">
          <div className="flex items-center space-x-4">
            {/* Home Button */}
            <button
              onClick={handleGoHome}
              className="p-2 bg-white/10 hover:bg-accent/40 text-white rounded-lg transition border border-white/20 hover:border-accent/50 flex items-center justify-center"
              title="Go to Home"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </button>

            <div className="relative">
              <span className="text-5xl">🏀</span>
              <div className="absolute -top-1 -right-1 w-5 h-5 bg-okta-blue rounded-full border-2 border-white flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            <div>
              <h1 className="text-white text-2xl font-bold">CourtEdge ProGear</h1>
              <p className="text-gray-300 text-sm">AI-Powered Basketball Equipment Sales</p>
            </div>
          </div>

          {/* Token Flow + Architecture */}
          <div className="flex items-center space-x-2">
            <Link
              href="/tokens"
              className="px-4 py-2.5 bg-white/10 hover:bg-accent/30 text-white rounded-lg transition border border-white/20 hover:border-accent/50 flex items-center gap-2 text-sm"
              title="Token exchanges, FGA checks, and demo controls"
            >
              <Key className="w-4 h-4" />
              <span className="hidden sm:inline">Token Flow</span>
            </Link>
            <Link
              href="/architecture"
              className="px-4 py-2.5 bg-white/10 hover:bg-accent/30 text-white rounded-lg transition border border-white/20 hover:border-accent/50 flex items-center gap-2 text-sm"
              title="How the system is wired together"
            >
              <GitBranch className="w-4 h-4" />
              <span className="hidden sm:inline">Architecture</span>
            </Link>
            <Link
              href="/fga"
              className="px-4 py-2.5 bg-white/10 hover:bg-accent/30 text-white rounded-lg transition border border-white/20 hover:border-accent/50 flex items-center gap-2 text-sm"
              title="Fine-Grained Authorization checks and demo controls"
            >
              <ShieldCheck className="w-4 h-4" />
              <span className="hidden sm:inline">FGA</span>
              {isFGASimulationEnabled ? (
                <span className="rounded-full bg-emerald-400/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-emerald-200">
                  On
                </span>
              ) : null}
            </Link>
          </div>

          <div className="flex items-center space-x-3">
            <ThemeSelector iconOnly />
            <div className="flex items-center gap-3">
              <span className="text-gray-200 text-sm">{session?.user?.email}</span>
              <button
                onClick={handleSignOut}
                className="flex items-center space-x-2 whitespace-nowrap rounded-lg border border-white/20 bg-white/10 px-5 py-2.5 text-white transition hover:border-accent/50 hover:bg-accent/30"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Chat - full width; token/FGA/approval detail lives on /tokens now */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex w-full flex-col bg-gradient-to-b from-slate-50 to-white dark:from-neutral-bg dark:to-primary-light">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-3xl mx-auto w-full">
            {chatMessages.length === 0 && (
              <div className="text-center py-8 max-w-2xl mx-auto">
                <div className="inline-block mb-4 relative">
                  <div className="absolute inset-0 bg-accent/20 rounded-full blur-2xl animate-pulse"></div>
                  <span className="text-6xl relative z-10">🏀</span>
                </div>
                <h2 className="mb-2 text-2xl font-bold text-slate-900 dark:text-white">Welcome, {session?.user?.name || 'Team Member'}!</h2>
                <p className="mb-6 text-slate-600 dark:text-gray-300">
                  Your AI-powered basketball equipment sales assistant is ready. Ask about orders, inventory, pricing, or customers.
                </p>

                <div className="mx-auto flex max-w-lg flex-col gap-2.5 text-left">
                  {(isFGASimulationEnabled ? fgaExampleQuestions : simpleExampleQuestions).map((question) => {
                    const isRead = question.action === 'read';
                    return (
                      <button
                        key={question.badge}
                        onClick={() => handleSendMessage(question.text)}
                        className="group flex min-h-14 items-center gap-3 rounded-xl border-2 border-accent/20 bg-white/95 px-3.5 py-2.5 text-left backdrop-blur-sm transition-all hover:border-accent hover:shadow-lg dark:bg-slate-900/95"
                      >
                        <span
                          className={`min-w-20 flex-shrink-0 rounded-md px-2 py-1 text-center text-[10px] font-bold uppercase tracking-wide ${
                            isRead
                              ? 'bg-emerald-100 text-emerald-700'
                              : question.action === 'large'
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-court-orange/15 text-court-orange'
                          }`}
                        >
                          {question.badge}
                        </span>
                        <span className="text-sm font-medium leading-snug text-gray-700 group-hover:text-primary dark:text-slate-200 dark:group-hover:text-white">
                          {question.text}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`flex items-start space-x-3 max-w-2xl ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                  <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-br from-court-orange to-accent'
                      : 'bg-gradient-to-br from-primary to-court-brown'
                  }`}>
                    {msg.role === 'user' ? (
                      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    ) : (
                      <span className="text-xl">🏀</span>
                    )}
                  </div>

                  <div className={`rounded-xl p-4 shadow-md ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-br from-accent to-court-orange text-white'
                      : 'bg-white border-2 border-neutral-border'
                  }`}>
                    {msg.role === 'assistant' ? (
                      <div className="text-gray-700 text-sm [&_p:last-child]:mb-0">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    )}
                    {msg.role === 'assistant' && getRouterSummary(msg.agentFlow) && (
                      <div className="text-[11px] font-mono text-okta-blue/80 mt-2 pt-2 border-t border-neutral-border/60">
                        {getRouterSummary(msg.agentFlow)}
                      </div>
                    )}
                    <div className={`text-xs mt-2 ${msg.role === 'user' ? 'text-white/70' : 'text-gray-400'}`}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-primary to-court-brown rounded-lg flex items-center justify-center">
                    <span className="text-xl animate-bounce">🏀</span>
                  </div>
                  <div className="bg-white border-2 border-accent/30 rounded-xl p-4 shadow-md">
                    <div className="flex items-center space-x-3">
                      <div className="flex space-x-2">
                        <div className="w-2.5 h-2.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="w-2.5 h-2.5 bg-court-orange rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="w-2.5 h-2.5 bg-court-brown rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                      </div>
                      <span className="text-sm text-gray-500">Processing with AI agents...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t-4 border-accent bg-gradient-to-r from-white via-accent/5 to-white px-6 py-4 shadow-2xl">
            <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="flex space-x-3 max-w-4xl mx-auto">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Ask about orders, inventory, pricing, or customers..."
                  className="w-full px-5 py-3 border-2 border-neutral-border rounded-xl focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition text-gray-700 placeholder-gray-400"
                  disabled={isLoading}
                />
                <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-30">
                  🏀
                </div>
              </div>
              <button
                type="submit"
                disabled={isLoading || !message.trim()}
                className="px-6 py-3 bg-gradient-to-r from-accent to-court-orange hover:from-court-orange hover:to-accent text-white rounded-xl font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg hover:shadow-xl flex items-center space-x-2 border-b-4 border-court-brown/50"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <span>Send</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
