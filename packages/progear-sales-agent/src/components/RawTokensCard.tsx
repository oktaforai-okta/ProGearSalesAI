'use client';

import { useState } from 'react';
import {
  Key, ChevronDown, ChevronUp, ChevronRight, ExternalLink, KeySquare, ShieldOff, TriangleAlert,
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
  id_jag_claims?: Record<string, any>;  // ID-JAG claims (unused for display, kept for counting)
}

interface Props {
  exchanges: TokenExchange[];
  idTokenClaims?: Record<string, any>;
  idTokenRaw?: string;  // Raw ID token JWT
}

// Shows the raw, signed JWT only - no in-house "decoded" view. The point is
// credibility: a self-built decoded-claims panel can look like theater to a
// skeptical viewer, but a real signed token that decodes cleanly on jwt.io
// (an independent, well-known tool nobody thinks we control) can't be faked.
//
// When a step was blocked rather than just not-yet-reached, say so explicitly
// instead of the generic "No token available" - the absence of a token here
// is the point being demonstrated (a policy denial), not a gap in the demo.
function TokenSection({
  title,
  rawToken,
  color,
  defaultOpen = false,
  blockedReason,
}: {
  title: string;
  rawToken?: string;
  color?: string;
  defaultOpen?: boolean;
  blockedReason?: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

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

  if (!rawToken) {
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
        <span className="text-xs text-gray-400 ml-auto">token available</span>
      </button>

      {isOpen && (
        <div className="bg-white">
          <div className="flex items-center justify-end px-3 py-2 border-b border-gray-100 bg-gray-50/50">
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
          </div>
          <div className="p-2">
            <div className="font-mono text-[10px] text-gray-700 bg-orange-50 p-2 rounded border border-orange-200 break-all whitespace-pre-wrap">
              {rawToken}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function RawTokensCard({ exchanges, idTokenRaw }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Keep the latest record per domain. Successful tokens, policy denials, and
  // system errors are all relevant evidence. A domain that was never invoked
  // has no exchange record and is correctly left out.
  const latestExchanges = exchanges.reduce((acc, exchange) => {
    const isRelevant =
      exchange.access_token ||
      exchange.id_jag_token ||
      exchange.access_denied ||
      exchange.status === 'error' ||
      exchange.error;
    if (isRelevant) {
      acc[exchange.agent] = exchange;
    }
    return acc;
  }, {} as Record<string, TokenExchange>);

  const relevantExchanges = Object.values(latestExchanges);
  const hasAnyTokens = !!idTokenRaw || relevantExchanges.length > 0;

  // Count total tokens (ID Token + ID-JAG tokens + Access tokens)
  const tokenCount = (idTokenRaw ? 1 : 0) +
    relevantExchanges.reduce((count, e) => {
      let c = 0;
      if (e.id_jag_token) c++;
      if (e.access_token) c++;
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
                {(exchange.id_jag_token || blocked) && (
                  <TokenSection
                    title={`Step 2: Cross-App Access Ticket Issued for ${exchange.agent_name} (ID-JAG Token)`}
                    rawToken={exchange.id_jag_token}
                    color="#6366f1"  // Indigo for ID-JAG
                    defaultOpen={false}
                    blockedReason={blocked}
                  />
                )}

                {/* Access Token (final) */}
                {(exchange.access_token || blocked) && (
                  <TokenSection
                    title={`Step 3: ${exchange.agent_name} Granted Access to Business Data (Access Token)`}
                    rawToken={exchange.access_token}
                    color={exchange.color}
                    defaultOpen={false}
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
