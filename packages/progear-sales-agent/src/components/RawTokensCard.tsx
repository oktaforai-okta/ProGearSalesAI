'use client';

import { useState } from 'react';
import { decodeJwt } from 'jose';
import {
  Key, ChevronDown, ChevronUp, ChevronRight, Copy, Check, ExternalLink,
  KeySquare, ShieldOff, TriangleAlert, Unlock, Lock, User, Bot,
  ShieldCheck, Flag, Clock,
} from 'lucide-react';

interface TokenExchange {
  agent: string;
  agent_name: string;
  color: string;
  success: boolean;
  access_denied: boolean;
  status: string;
  scopes: string[];
  error?: string;
  fga_denied?: boolean;
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

// When a step was blocked rather than just not-yet-reached, say so explicitly
// instead of the generic "No token available" - the absence of a token here
// is the point being demonstrated (a policy denial), not a gap in the demo.

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
  governance: { label: 'Governance', icon: Flag, text: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-400' },
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

const CATEGORY_ORDER: (keyof typeof CATEGORIES)[] = [
  'identity', 'agent', 'authorization', 'governance', 'timing', 'technical',
];

function categoryFor(key: string): keyof typeof CATEGORIES {
  return CLAIM_CATEGORY[key] || 'technical';
}

function formatClaimValue(value: any): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function decodeToken(rawToken?: string): Record<string, any> | undefined {
  if (!rawToken) return undefined;
  try {
    return decodeJwt(rawToken);
  } catch {
    return undefined;
  }
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error(`Failed to copy ${label}:`, error);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex items-center gap-1 px-2 py-1 text-[10px] bg-gray-100 hover:bg-gray-200 rounded transition text-gray-600"
      title={`Copy ${label}`}
    >
      {copied ? (
        <>
          <Check className="w-3 h-3 text-green-600" />
          <span className="text-green-600">Copied</span>
        </>
      ) : (
        <>
          <Copy className="w-3 h-3" />
          Copy
        </>
      )}
    </button>
  );
}

function DecodedTokenView({ claims }: { claims?: Record<string, any> }) {
  const [isOpen, setIsOpen] = useState(true);
  const grouped: Record<string, [string, any][]> = {};

  if (claims) {
    for (const entry of Object.entries(claims)) {
      const category = categoryFor(entry[0]);
      (grouped[category] ||= []).push(entry);
    }
    for (const category of Object.keys(grouped)) {
      grouped[category].sort(([a], [b]) => a.localeCompare(b));
    }
  }

  const populatedCategories = CATEGORY_ORDER.filter((category) => grouped[category]?.length);
  const claimCount = claims ? Object.keys(claims).length : 0;

  return (
    <div className="border border-blue-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full flex items-center gap-2 px-3 py-2 bg-blue-50 hover:bg-blue-100 transition text-left"
      >
        {isOpen ? <ChevronDown className="w-4 h-4 text-blue-600" /> : <ChevronRight className="w-4 h-4 text-blue-600" />}
        <Unlock className="w-4 h-4 text-blue-600" />
        <span className="text-xs font-semibold text-blue-800">Decoded claims</span>
        <span className="text-[10px] text-blue-600 ml-auto">{claimCount} claims</span>
      </button>

      {isOpen && (
        <div className="p-3 space-y-3 bg-white border-t border-blue-100">
          {claims && (
            <div className="flex justify-end">
              <CopyButton text={JSON.stringify(claims, null, 2)} label="decoded claims" />
            </div>
          )}
          {populatedCategories.length > 0 ? (
            populatedCategories.map((category) => {
              const meta = CATEGORIES[category];
              const Icon = meta.icon;
              return (
                <div key={category}>
                  <div className={`flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide mb-1 ${meta.text}`}>
                    <Icon className="w-3 h-3" />
                    {meta.label}
                  </div>
                  <div className="space-y-1">
                    {grouped[category].map(([key, value]) => {
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
                            <pre className="mt-1 text-gray-800 whitespace-pre-wrap break-words overflow-x-auto">
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
            <div className="text-xs text-gray-400 text-center py-4">Unable to decode this token</div>
          )}
        </div>
      )}
    </div>
  );
}

function EncodedTokenView({ rawToken }: { rawToken?: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border border-orange-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full flex items-center gap-2 px-3 py-2 bg-orange-50 hover:bg-orange-100 transition text-left"
      >
        {isOpen ? <ChevronDown className="w-4 h-4 text-orange-600" /> : <ChevronRight className="w-4 h-4 text-orange-600" />}
        <Lock className="w-4 h-4 text-orange-600" />
        <span className="text-xs font-semibold text-orange-800">Encoded JWT</span>
        <span className="text-[10px] text-orange-600 ml-auto">signed token</span>
      </button>

      {isOpen && (
        <div className="bg-white border-t border-orange-100">
          <div className="flex items-center justify-end gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50/50">
            {rawToken && <CopyButton text={rawToken} label="encoded JWT" />}
            {rawToken && (
              <a
                href={`https://jwt.io/#token=${encodeURIComponent(rawToken)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-2 py-1 text-[10px] bg-gray-100 hover:bg-gray-200 rounded transition text-gray-600"
                title="Open this signed token directly in jwt.io for independent verification"
              >
                <ExternalLink className="w-3 h-3" />
                Verify on jwt.io
              </a>
            )}
          </div>
          <div className="p-2">
            {rawToken ? (
              <div className="font-mono text-[10px] text-gray-700 bg-orange-50 p-2 rounded border border-orange-200 break-all whitespace-pre-wrap">
                {rawToken}
              </div>
            ) : (
              <div className="text-xs text-gray-400 text-center py-4">Encoded token not available</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TokenSection({
  title,
  claims,
  rawToken,
  color,
  defaultOpen = true,
  blockedReason,
}: {
  title: string;
  claims?: Record<string, any>;
  rawToken?: string;
  color?: string;
  defaultOpen?: boolean;
  blockedReason?: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const decodedClaims = claims && Object.keys(claims).length > 0 ? claims : decodeToken(rawToken);

  if (blockedReason) {
    return (
      <div className="border border-red-200 rounded-lg overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 bg-red-50 text-red-700 text-sm">
          <ShieldOff className="w-4 h-4 flex-shrink-0" />
          <span className="font-medium">{title}</span>
          <span className="text-xs text-red-600 ml-auto flex-shrink-0">Blocked by policy</span>
        </div>
        <div className="px-3 py-2 bg-white text-xs text-red-700 border-t border-red-100">
          {blockedReason}
        </div>
      </div>
    );
  }

  if (!rawToken && !decodedClaims) {
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

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
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
        <span className="text-xs text-gray-400 ml-auto">token available</span>
      </button>

      {isOpen && (
        <div className="bg-white">
          <div className="p-3 space-y-2">
            <DecodedTokenView claims={decodedClaims} />
            <EncodedTokenView rawToken={rawToken} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function RawTokensCard({ exchanges, idTokenClaims, idTokenRaw }: Props) {
  // The Token Flow page is a demonstration surface: show the complete proof
  // chain immediately, while preserving the option to collapse it manually.
  const [isExpanded, setIsExpanded] = useState(true);

  // Keep the latest record per domain. Successful tokens, policy denials, and
  // system errors are all relevant evidence. A domain that was never invoked
  // has no exchange record and is correctly left out.
  const latestExchanges = exchanges.reduce((acc, exchange) => {
    const isRelevant =
      exchange.access_token ||
      exchange.id_jag_token ||
      exchange.token_claims ||
      exchange.id_jag_claims ||
      exchange.access_denied ||
      exchange.status === 'error' ||
      exchange.error;
    if (isRelevant) {
      acc[exchange.agent] = exchange;
    }
    return acc;
  }, {} as Record<string, TokenExchange>);

  const relevantExchanges = Object.values(latestExchanges);
  const hasAnyTokens = !!idTokenRaw || !!idTokenClaims || relevantExchanges.length > 0;

  // Count total tokens (ID Token + ID-JAG tokens + Access tokens)
  const tokenCount = (idTokenRaw || idTokenClaims ? 1 : 0) +
    relevantExchanges.reduce((count, e) => {
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
              <div className="text-[10px] text-gray-500 flex items-center justify-start gap-1.5">
                <KeySquare className="w-3 h-3" />
                <span className="font-semibold">Token Flow:</span> ID Token → ID-JAG Token → Access Token
              </div>
            </div>
          )}

          {/* ID Token (User's original token) */}
          <TokenSection
            title="Step 1: User Authenticated to Okta for AI Agent Interface (ID Token)"
            claims={idTokenClaims}
            rawToken={idTokenRaw}
            color="#007dc1"
            defaultOpen={true}
          />

          {/* Agent Token Exchanges - ID-JAG and Access Token for each */}
          {relevantExchanges.map((exchange, idx) => {
            const blocked = exchange.access_denied
              ? exchange.error || `Access denied for ${exchange.agent_name}`
              : undefined;
            const systemError = !blocked && exchange.status === 'error'
              ? exchange.error || `Token exchange failed for ${exchange.agent_name}`
              : undefined;
            return (
              <div key={idx} className="space-y-2">
                {systemError && (
                  <div className="border border-amber-200 rounded-lg overflow-hidden">
                    <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 text-amber-800 text-sm">
                      <TriangleAlert className="w-4 h-4 flex-shrink-0" />
                      <span className="font-medium">{exchange.agent_name} token exchange failed</span>
                    </div>
                    <div className="px-3 py-2 bg-white text-xs text-amber-800 border-t border-amber-100">
                      {systemError}
                    </div>
                  </div>
                )}

                {/* ID-JAG Token (intermediate) */}
                {(exchange.id_jag_token || exchange.id_jag_claims || blocked) && (
                  <TokenSection
                    title={`Step 2: Cross-App Access Ticket Issued for ${exchange.agent_name} (ID-JAG Token)`}
                    claims={exchange.id_jag_claims}
                    rawToken={exchange.id_jag_token}
                    color="#6366f1"  // Indigo for ID-JAG
                    blockedReason={blocked}
                  />
                )}

                {/* Access Token (final) */}
                {(exchange.access_token || exchange.token_claims || blocked) && (
                  <TokenSection
                    title={`Step 3: ${exchange.agent_name} Granted Access to Business Data (Access Token)`}
                    claims={exchange.token_claims}
                    rawToken={exchange.access_token}
                    color={exchange.color}
                    blockedReason={blocked}
                  />
                )}
              </div>
            );
          })}

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
