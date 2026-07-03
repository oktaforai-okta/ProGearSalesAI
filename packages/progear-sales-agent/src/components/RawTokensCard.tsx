'use client';

import { useState } from 'react';
import {
  Key, ChevronDown, ChevronUp, ChevronRight, Copy, Check, Lock, Unlock,
  User, Bot, ShieldCheck, Flag, Clock, KeySquare,
} from 'lucide-react';

interface TokenExchange {
  agent: string;
  agent_name: string;
  color: string;
  success: boolean;
  access_denied: boolean;
  status: string;
  scopes: string[];
  token_claims?: Record<string, any>;
  access_token?: string;  // Raw access token JWT
  id_jag_token?: string;  // Raw ID-JAG token (intermediate)
  id_jag_claims?: Record<string, any>;  // Decoded ID-JAG claims
}

interface Props {
  exchanges: TokenExchange[];
  idTokenClaims?: Record<string, any>;
  idTokenRaw?: string;  // Raw ID token JWT
}

// Every claim gets bucketed into one of these categories so a reader can
// tell at a glance "who is this" vs "what can they do" vs "just plumbing" -
// a flat alphabetical list of key:value pairs made every claim look equally
// important, which was the actual readability complaint.
type ClaimCategory = {
  label: string;
  icon: typeof User;
  text: string;
  bg: string;
  border: string;
};

const CATEGORIES: Record<string, ClaimCategory> = {
  identity: { label: 'Identity', icon: User, text: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-400' },
  agent: { label: 'Agent', icon: Bot, text: 'text-violet-700', bg: 'bg-violet-50', border: 'border-violet-400' },
  authorization: { label: 'Authorization', icon: ShieldCheck, text: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-400' },
  governance: { label: 'FGA / Governance', icon: Flag, text: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-400' },
  timing: { label: 'Timing', icon: Clock, text: 'text-slate-600', bg: 'bg-slate-50', border: 'border-slate-300' },
  technical: { label: 'Technical', icon: Lock, text: 'text-gray-500', bg: 'bg-gray-50', border: 'border-gray-300' },
};

const CLAIM_CATEGORY: Record<string, keyof typeof CATEGORIES> = {
  sub: 'identity', email: 'identity', name: 'identity', given_name: 'identity',
  family_name: 'identity', preferred_username: 'identity', login: 'identity',
  act: 'agent', 'act.sub': 'agent', actor: 'agent',
  scp: 'authorization', scope: 'authorization', aud: 'authorization', groups: 'authorization',
  Manager: 'governance', Vacation: 'governance', Clearance: 'governance',
  is_on_vacation: 'governance', is_a_manager: 'governance', clearance_level: 'governance',
  iat: 'timing', exp: 'timing', auth_time: 'timing', nbf: 'timing',
};

// Category display order - identity/agent/authorization/governance first
// since those answer "who, what, allowed to do what" (the actual demo
// story); timing and technical plumbing sink to the bottom.
const CATEGORY_ORDER: (keyof typeof CATEGORIES)[] = [
  'identity', 'agent', 'authorization', 'governance', 'timing', 'technical',
];

function categoryFor(key: string): keyof typeof CATEGORIES {
  return CLAIM_CATEGORY[key] || 'technical';
}

// Format claim value for display
function formatClaimValue(value: any): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

// Copy button component
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 px-2 py-1 text-[10px] bg-gray-100 hover:bg-gray-200 rounded transition"
      title={`Copy ${label}`}
    >
      {copied ? (
        <>
          <Check className="w-3 h-3 text-green-600" />
          <span className="text-green-600">Copied!</span>
        </>
      ) : (
        <>
          <Copy className="w-3 h-3 text-gray-500" />
          <span className="text-gray-500">Copy</span>
        </>
      )}
    </button>
  );
}

function TokenSection({
  title,
  claims,
  rawToken,
  color,
  defaultOpen = false
}: {
  title: string;
  claims?: Record<string, any>;
  rawToken?: string;
  color?: string;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [showRaw, setShowRaw] = useState(false);

  const hasData = (claims && Object.keys(claims).length > 0) || rawToken;

  if (!hasData) {
    return (
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 text-gray-500 text-sm">
          <ChevronRight className="w-4 h-4" />
          <span>{title}</span>
          <span className="text-xs text-gray-400 ml-auto">No token available</span>
        </div>
      </div>
    );
  }

  // Group claims by category, in CATEGORY_ORDER, alphabetical within a group.
  const grouped: Record<string, [string, any][]> = {};
  if (claims) {
    for (const entry of Object.entries(claims)) {
      const cat = categoryFor(entry[0]);
      (grouped[cat] ||= []).push(entry);
    }
    for (const cat of Object.keys(grouped)) {
      grouped[cat].sort(([a], [b]) => a.localeCompare(b));
    }
  }
  const populatedCategories = CATEGORY_ORDER.filter((c) => grouped[c]?.length);
  const totalClaims = claims ? Object.keys(claims).length : 0;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition text-left"
      >
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-500" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-500" />
        )}
        {color && (
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: color }}
          />
        )}
        <span className="text-sm font-medium text-gray-700">{title}</span>
        <span className="text-xs text-gray-400 ml-auto">
          {claims ? `${totalClaims} claims` : 'token available'}
        </span>
      </button>

      {isOpen && (
        <div className="bg-white">
          {/* Toggle between Raw and Decoded */}
          <div className="flex items-center justify-end gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50/50">
            <button
              onClick={() => setShowRaw(false)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition ${
                !showRaw
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Unlock className="w-3 h-3" />
              Decoded
            </button>
            <button
              onClick={() => setShowRaw(true)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition ${
                showRaw
                  ? 'bg-orange-100 text-orange-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Lock className="w-3 h-3" />
              Encoded (JWT)
            </button>
            {rawToken && showRaw && (
              <CopyButton text={rawToken} label="JWT" />
            )}
          </div>

          {/* Content */}
          {showRaw ? (
            <div className="p-2">
              {rawToken ? (
                <div className="font-mono text-[10px] text-gray-700 bg-orange-50 p-2 rounded border border-orange-200 break-all whitespace-pre-wrap">
                  {rawToken}
                </div>
              ) : (
                <div className="text-xs text-gray-400 text-center py-4">
                  Raw token not available
                </div>
              )}
            </div>
          ) : (
            <div className="p-2 space-y-2.5">
              {populatedCategories.length > 0 ? (
                populatedCategories.map((cat) => {
                  const meta = CATEGORIES[cat];
                  const Icon = meta.icon;
                  return (
                    <div key={cat}>
                      <div className={`flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide mb-1 ${meta.text}`}>
                        <Icon className="w-3 h-3" />
                        {meta.label}
                      </div>
                      <div className="space-y-1">
                        {grouped[cat].map(([key, value]) => {
                          const isObject = value !== null && typeof value === 'object';
                          return (
                            <div
                              key={key}
                              className={`rounded border-l-2 font-mono text-[11px] ${meta.bg} ${meta.border} ${
                                isObject ? 'px-2 py-1.5' : 'flex gap-2 px-2 py-1.5'
                              }`}
                            >
                              <span className={`flex-shrink-0 font-semibold ${meta.text}`}>{key}:</span>
                              {isObject ? (
                                <pre className="mt-1 text-gray-800 whitespace-pre overflow-x-auto">
                                  {JSON.stringify(value, null, 2)}
                                </pre>
                              ) : (
                                <span className="break-all text-gray-800">{formatClaimValue(value)}</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="text-xs text-gray-400 text-center py-4">
                  No decoded claims available
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RawTokensCard({ exchanges, idTokenClaims, idTokenRaw }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Filter exchanges that have token data and keep only the latest per agent
  const latestExchanges = exchanges.reduce((acc, exchange) => {
    const hasTokenData = (exchange.token_claims && Object.keys(exchange.token_claims).length > 0)
      || exchange.access_token
      || exchange.id_jag_token;
    if (hasTokenData) {
      acc[exchange.agent] = exchange; // Keep only latest per agent
    }
    return acc;
  }, {} as Record<string, TokenExchange>);

  const exchangesWithTokens = Object.values(latestExchanges);
  const hasAnyTokens = idTokenClaims || idTokenRaw || exchangesWithTokens.length > 0;

  // Count total tokens (ID Token + ID-JAG tokens + Access tokens)
  const tokenCount = (idTokenClaims || idTokenRaw ? 1 : 0) +
    exchangesWithTokens.reduce((count, e) => {
      let c = 0;
      if (e.id_jag_token || e.id_jag_claims) c++;
      if (e.access_token || e.token_claims) c++;
      return count + c;
    }, 0);

  return (
    <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
      {/* Header - Always visible, clickable to expand/collapse */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full bg-gradient-to-r from-gray-700 to-gray-800 px-4 py-3 border-b border-neutral-border flex items-center justify-between hover:from-gray-600 hover:to-gray-700 transition"
      >
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Key className="w-5 h-5" />
          Step-by-Step Token Flow
        </h3>
        <div className="flex items-center gap-2">
          {!isExpanded && hasAnyTokens && (
            <span className="text-xs text-gray-400">
              {tokenCount} token(s)
            </span>
          )}
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-white" />
          ) : (
            <ChevronDown className="w-5 h-5 text-white" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="p-4 space-y-3">
          {/* Token Flow legend -- lives at the top now (right-aligned) so
              it's the first thing read, rather than a footer someone has
              to scroll past every step to find. */}
          {hasAnyTokens && (
            <div className="pb-3 border-b border-gray-100">
              <div className="text-[10px] text-gray-500 flex items-center justify-end gap-1.5">
                <KeySquare className="w-3 h-3" />
                <span className="font-semibold">Token Flow:</span> ID Token → ID-JAG Token → Access Token
              </div>
            </div>
          )}

          {/* ID Token (User's original token) -- categories are already
              labeled inline within each expanded step below, so a separate
              top-level legend here was pure duplication. */}
          <TokenSection
            title="Step 1: User Authenticated to Okta for AI Agent Interface (ID Token)"
            claims={idTokenClaims}
            rawToken={idTokenRaw}
            color="#007dc1"
            defaultOpen={true}
          />

          {/* Agent Token Exchanges - ID-JAG and Access Token for each */}
          {exchangesWithTokens.map((exchange, idx) => (
            <div key={idx} className="space-y-2">
              {/* ID-JAG Token (intermediate) */}
              {(exchange.id_jag_token || exchange.id_jag_claims) && (
                <TokenSection
                  title={`Step 2: Cross-App Access Ticket Issued for ${exchange.agent_name} (ID-JAG Token)`}
                  claims={exchange.id_jag_claims}
                  rawToken={exchange.id_jag_token}
                  color="#6366f1"  // Indigo for ID-JAG
                  defaultOpen={false}
                />
              )}

              {/* Access Token (final) */}
              {(exchange.access_token || exchange.token_claims) && (
                <TokenSection
                  title={`Step 3: ${exchange.agent_name} Granted Access to Business Data (Access Token)`}
                  claims={exchange.token_claims}
                  rawToken={exchange.access_token}
                  color={exchange.color}
                  defaultOpen={false}
                />
              )}
            </div>
          ))}

          {/* No tokens message */}
          {!hasAnyTokens && (
            <div className="text-center py-4 text-gray-400">
              <Key className="w-6 h-6 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No token data available</p>
              <p className="text-xs">Send a message to see token exchanges</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
