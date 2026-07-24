'use client';

import { useState } from 'react';
import {
  Key, ChevronDown, ChevronUp, ChevronRight, Copy, Check, ExternalLink, KeySquare,
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
  id_jag_claims?: Record<string, any>;  // ID-JAG claims (unused for display, kept for counting)
}

interface Props {
  exchanges: TokenExchange[];
  idTokenClaims?: Record<string, any>;
  idTokenRaw?: string;  // Raw ID token JWT
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

// Shows the raw, signed JWT only - no in-house "decoded" view. The point is
// credibility: a self-built decoded-claims panel can look like theater to a
// skeptical viewer, but a real signed token that decodes cleanly on jwt.io
// (an independent, well-known tool nobody thinks we control) can't be faked.
function TokenSection({
  title,
  rawToken,
  color,
  defaultOpen = false,
}: {
  title: string;
  rawToken?: string;
  color?: string;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

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
          <div className="flex items-center justify-end gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50/50">
            <CopyButton text={rawToken} label="JWT" />
            <a
              href="https://jwt.io"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-2 py-1 text-[10px] bg-gray-100 hover:bg-gray-200 rounded transition text-gray-600"
              title="Copy the token above, then verify it independently on jwt.io"
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

  // Filter exchanges that have token data and keep only the latest per agent
  const latestExchanges = exchanges.reduce((acc, exchange) => {
    const hasTokenData = exchange.access_token || exchange.id_jag_token;
    if (hasTokenData) {
      acc[exchange.agent] = exchange; // Keep only latest per agent
    }
    return acc;
  }, {} as Record<string, TokenExchange>);

  const exchangesWithTokens = Object.values(latestExchanges);
  const hasAnyTokens = !!idTokenRaw || exchangesWithTokens.length > 0;

  // Count total tokens (ID Token + ID-JAG tokens + Access tokens)
  const tokenCount = (idTokenRaw ? 1 : 0) +
    exchangesWithTokens.reduce((count, e) => {
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
          {exchangesWithTokens.map((exchange, idx) => (
            <div key={idx} className="space-y-2">
              {/* ID-JAG Token (intermediate) */}
              {exchange.id_jag_token && (
                <TokenSection
                  title={`Step 2: Cross-App Access Ticket Issued for ${exchange.agent_name} (ID-JAG Token)`}
                  rawToken={exchange.id_jag_token}
                  color="#6366f1"  // Indigo for ID-JAG
                  defaultOpen={false}
                />
              )}

              {/* Access Token (final) */}
              {exchange.access_token && (
                <TokenSection
                  title={`Step 3: ${exchange.agent_name} Granted Access to Business Data (Access Token)`}
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
