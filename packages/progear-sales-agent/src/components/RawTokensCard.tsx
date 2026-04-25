'use client';

import { useState } from 'react';
import { Key, ChevronDown, ChevronUp, ChevronRight } from 'lucide-react';

interface TokenExchange {
  agent: string;
  agent_name: string;
  color: string;
  success: boolean;
  access_denied: boolean;
  status: string;
  scopes: string[];
  token_claims?: Record<string, any>;
}

interface Props {
  exchanges: TokenExchange[];
  idTokenClaims?: Record<string, any>;
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

function TokenSection({
  title,
  claims,
  color,
  defaultOpen = false
}: {
  title: string;
  claims?: Record<string, any>;
  color?: string;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!claims || Object.keys(claims).length === 0) {
    return (
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 text-gray-500 text-sm">
          <ChevronRight className="w-4 h-4" />
          <span>{title}</span>
          <span className="text-xs text-gray-400 ml-auto">No claims available</span>
        </div>
      </div>
    );
  }

  // Sort claims: highlighted first, then alphabetically
  const sortedClaims = Object.entries(claims).sort(([a], [b]) => {
    const aHighlight = HIGHLIGHT_CLAIMS.includes(a);
    const bHighlight = HIGHLIGHT_CLAIMS.includes(b);
    if (aHighlight && !bHighlight) return -1;
    if (!aHighlight && bHighlight) return 1;
    return a.localeCompare(b);
  });

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
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
          {Object.keys(claims).length} claims
        </span>
      </button>

      {isOpen && (
        <div className="p-2 bg-white max-h-48 overflow-y-auto">
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
        </div>
      )}
    </div>
  );
}

export default function RawTokensCard({ exchanges, idTokenClaims }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Filter exchanges that have token claims
  const exchangesWithClaims = exchanges.filter(e => e.token_claims && Object.keys(e.token_claims).length > 0);
  const hasAnyTokens = idTokenClaims || exchangesWithClaims.length > 0;

  return (
    <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
      {/* Header - Always visible, clickable to expand/collapse */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full bg-gradient-to-r from-gray-700 to-gray-800 px-4 py-3 border-b border-neutral-border flex items-center justify-between hover:from-gray-600 hover:to-gray-700 transition"
      >
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Key className="w-5 h-5" />
          Raw Tokens
        </h3>
        <div className="flex items-center gap-2">
          {!isExpanded && hasAnyTokens && (
            <span className="text-xs text-gray-400">
              {(idTokenClaims ? 1 : 0) + exchangesWithClaims.length} token(s)
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
        <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
          {/* ID Token */}
          <TokenSection
            title="ID Token (User)"
            claims={idTokenClaims}
            defaultOpen={true}
          />

          {/* Agent Tokens */}
          {exchangesWithClaims.map((exchange, idx) => (
            <TokenSection
              key={idx}
              title={`${exchange.agent_name} Token`}
              claims={exchange.token_claims}
              color={exchange.color}
              defaultOpen={false}
            />
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
