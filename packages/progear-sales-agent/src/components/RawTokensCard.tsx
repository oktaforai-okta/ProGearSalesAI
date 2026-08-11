'use client';

import { useState } from 'react';
import {
  CheckCircle2, Clock3, Key, ChevronDown, ChevronUp, ChevronRight, ExternalLink,
  KeySquare, ShieldCheck, ShieldOff, TriangleAlert, XCircle,
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
  resource_token_validated?: boolean;
  resource_token_kid?: string;
  resource_validation_error?: string;
}

interface AuthorizationDecision {
  agent: string;
  mode: 'simple' | 'fga';
  engine: string;
  operation: 'read' | 'write';
  quantity?: number | null;
  role_level?: number;
  role_name?: string;
  decision: 'allow' | 'deny' | 'approval_required';
  outcome: 'authorized' | 'executed' | 'blocked' | 'awaiting_approval';
  reason: string;
  relation?: string;
  request_id?: string;
  approval_role?: string | null;
  token_issued?: boolean;
  token_validated?: boolean;
}

interface Props {
  exchanges: TokenExchange[];
  decisions: AuthorizationDecision[];
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
  claims,
  stageNote,
}: {
  title: string;
  rawToken?: string;
  color?: string;
  defaultOpen?: boolean;
  blockedReason?: string;
  claims?: Record<string, any>;
  stageNote?: string;
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
        <span className="text-xs text-emerald-600 ml-auto">issued</span>
      </button>

      <div className="border-t border-gray-100 bg-white px-3 py-2">
        {stageNote ? <p className="mb-2 text-[11px] text-gray-600">{stageNote}</p> : null}
        {claims ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-gray-500">
            {claims.jti ? <span>jti …{String(claims.jti).slice(-12)}</span> : null}
            {claims.aud ? <span>aud {Array.isArray(claims.aud) ? claims.aud.join(', ') : String(claims.aud)}</span> : null}
            {claims.scp || claims.scope ? (
              <span>scope {Array.isArray(claims.scp) ? claims.scp.join(' ') : String(claims.scope ?? claims.scp)}</span>
            ) : null}
          </div>
        ) : null}
      </div>

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

function DecisionSection({ decision }: { decision: AuthorizationDecision }) {
  const presentation = decision.outcome === 'executed'
    ? {
        Icon: CheckCircle2,
        label: 'Executed',
        classes: 'border-emerald-200 bg-emerald-50 text-emerald-800',
      }
    : decision.outcome === 'awaiting_approval'
      ? {
          Icon: Clock3,
          label: `Waiting for ${decision.approval_role ?? 'VP'}`,
          classes: 'border-amber-200 bg-amber-50 text-amber-800',
        }
      : decision.outcome === 'blocked'
        ? {
            Icon: XCircle,
            label: 'Blocked — no inventory change',
            classes: 'border-red-200 bg-red-50 text-red-800',
          }
        : {
            Icon: ShieldCheck,
            label: 'Authorized',
            classes: 'border-blue-200 bg-blue-50 text-blue-800',
          };
  const { Icon } = presentation;
  const modeLabel = decision.mode === 'fga' ? 'FGA' : 'Simple role policy';

  return (
    <div className={`rounded-lg border p-3 ${presentation.classes}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Icon className="h-4 w-4" />
        <span className="text-sm font-semibold">Step 4: {presentation.label}</span>
        <span className="ml-auto rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide">
          {modeLabel}
        </span>
      </div>
      <p className="mt-1 text-xs leading-relaxed">{decision.reason}</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] opacity-80">
        <span>{decision.role_level} — {decision.role_name}</span>
        <span>{decision.operation}{decision.quantity ? ` · ${decision.quantity.toLocaleString()} units` : ''}</span>
        {decision.relation ? <span className="font-mono">{decision.relation}</span> : null}
        {decision.request_id ? <span className="font-mono">request {decision.request_id}</span> : null}
      </div>
    </div>
  );
}

export default function RawTokensCard({ exchanges, decisions, idTokenRaw }: Props) {
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
  const latestDecisions = decisions.reduce((acc, decision) => {
    acc[decision.agent] = decision;
    return acc;
  }, {} as Record<string, AuthorizationDecision>);
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
              {tokenCount} signed artifact(s)
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
                <span className="font-semibold">Proof chain:</span> ID Token → ID-JAG → Scoped Resource Token → Business Decision
              </div>
              <p className="mt-1 text-[11px] text-gray-600">
                A scoped token lets the request reach Inventory. It does not mean the requested write was authorized or executed.
              </p>
            </div>
          )}

          {/* ID Token (User's original token) */}
          <TokenSection
            title="Step 1: User Authenticated to Okta for AI Agent Interface (ID Token)"
            rawToken={idTokenRaw}
            color="#007dc1"
            defaultOpen={false}
            stageNote="The employee signed in. This token is not an Inventory write decision."
          />

          {/* Agent Token Exchanges - ID-JAG and Access Token for each */}
          {relevantExchanges.map((exchange) => {
            const blocked = exchange.access_denied
              ? exchange.error || `Access denied for ${exchange.agent_name}`
              : undefined;
            const systemError = !blocked && exchange.status === 'error'
              ? exchange.error || `Token exchange failed for ${exchange.agent_name}`
              : undefined;
            return (
              <div key={exchange.agent} className="space-y-2">
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
                    claims={exchange.id_jag_claims}
                    color="#6366f1"  // Indigo for ID-JAG
                    defaultOpen={false}
                    blockedReason={blocked}
                    stageNote="Okta delegated this employee + agent request to the Inventory authorization server."
                  />
                )}

                {/* Access Token (final) */}
                {(exchange.access_token || blocked) && (
                  <TokenSection
                    title={`Step 3: Scoped token issued for ${exchange.agent_name}`}
                    rawToken={exchange.access_token}
                    claims={exchange.token_claims}
                    color={exchange.color}
                    defaultOpen={false}
                    blockedReason={blocked}
                    stageNote="Coarse resource access only. The role/quantity policy still decides whether this action may execute."
                  />
                )}

                {exchange.access_token ? (
                  <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${
                    exchange.resource_token_validated
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                      : 'border-red-200 bg-red-50 text-red-800'
                  }`}>
                    {exchange.resource_token_validated
                      ? <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                      : <ShieldOff className="mt-0.5 h-4 w-4 shrink-0" />}
                    <div>
                      <span className="font-semibold">
                        {exchange.resource_token_validated ? 'Inventory validated the token' : 'Inventory rejected the token'}
                      </span>
                      <p className="mt-0.5">
                        {exchange.resource_token_validated
                          ? 'Signature, issuer, audience, expiry, agent identity, delegated user, and scope passed.'
                          : exchange.resource_validation_error ?? 'Resource-token validation did not pass.'}
                      </p>
                    </div>
                  </div>
                ) : null}

                {latestDecisions[exchange.agent] ? (
                  <DecisionSection decision={latestDecisions[exchange.agent]} />
                ) : null}
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
