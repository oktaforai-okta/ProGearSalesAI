'use client';

import { useState } from 'react';
import { Key, ChevronDown, ChevronUp, ChevronRight, Copy, Check, Lock, Unlock } from 'lucide-react';

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

// Format claim value for display
function formatClaimValue(value: any): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

// Claims to highlight (important for demo)
const HIGHLIGHT_CLAIMS = ['sub', 'email', 'aud', 'scope', 'scp', 'Vacation', 'is_on_vacation', 'groups'];

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

  // Sort claims: highlighted first, then alphabetically
  const sortedClaims = claims ? Object.entries(claims).sort(([a], [b]) => {
    const aHighlight = HIGHLIGHT_CLAIMS.includes(a);
    const bHighlight = HIGHLIGHT_CLAIMS.includes(b);
    if (aHighlight && !bHighlight) return -1;
    if (!aHighlight && bHighlight) return 1;
    return a.localeCompare(b);
  }) : [];

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
          {claims ? `${Object.keys(claims).length} claims` : 'token available'}
        </span>
      </button>

      {isOpen && (
        <div className="bg-white">
          {/* Toggle between Raw and Decoded */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50/50">
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
              <div className="ml-auto">
                <CopyButton text={rawToken} label="JWT" />
              </div>
            )}
          </div>

          {/* Content */}
          {showRaw ? (
            // Raw JWT display
            <div className="p-2 max-h-48 overflow-y-auto">
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
            // Decoded claims display
            <div className="p-2 max-h-48 overflow-y-auto">
              {sortedClaims.length > 0 ? (
                <div className="font-mono text-[11px] space-y-1">
                  {sortedClaims.map(([key, value]) => {
                    const isHighlighted = HIGHLIGHT_CLAIMS.includes(key);
                    const displayValue = formatClaimValue(value);

                    return (
                      <div
                        key={key}
                        className={`flex gap-2 px-2 py-1 rounded ${
                          isHighlighted ? 'bg-blue-50' : 'hover:bg-gray-50'
                        }`}
                      >
                        <span className={`flex-shrink-0 ${
                          isHighlighted ? 'text-blue-700 font-semibold' : 'text-gray-600'
                        }`}>
                          {key}:
                        </span>
                        <span className={`break-all ${
                          isHighlighted ? 'text-blue-900' : 'text-gray-800'
                        }`}>
                          {displayValue}
                        </span>
                      </div>
                    );
                  })}
                </div>
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
        <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
          {/* ID Token (User's original token) */}
          <TokenSection
            title="Step 1: User Authenticated to Okta for Chat Bot Interface"
            claims={idTokenClaims}
            rawToken={idTokenRaw}
            defaultOpen={true}
          />

          {/* Agent Token Exchanges - ID-JAG and Access Token for each */}
          {exchangesWithTokens.map((exchange, idx) => (
            <div key={idx} className="space-y-2">
              {/* ID-JAG Token (intermediate) */}
              {(exchange.id_jag_token || exchange.id_jag_claims) && (
                <TokenSection
                  title={`Step 2: Cross-App Access Ticket Issued for ${exchange.agent_name}`}
                  claims={exchange.id_jag_claims}
                  rawToken={exchange.id_jag_token}
                  color="#6366f1"  // Indigo for ID-JAG
                  defaultOpen={false}
                />
              )}

              {/* Access Token (final) */}
              {(exchange.access_token || exchange.token_claims) && (
                <TokenSection
                  title={`Step 3: ${exchange.agent_name} Granted Access to Business Data`}
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

          {/* Token Flow Legend */}
          {hasAnyTokens && (
            <div className="pt-3 border-t border-gray-100">
              <div className="text-[10px] text-gray-500">
                <span className="font-semibold">Token Flow:</span> ID Token → ID-JAG Token → Access Token
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
