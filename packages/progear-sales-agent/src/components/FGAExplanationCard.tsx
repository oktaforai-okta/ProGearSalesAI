'use client';

import { CheckCircle, XCircle, Shield, Palmtree, User, Database, ArrowRight, Info } from 'lucide-react';

interface FGACheck {
  agent: string;
  allowed: boolean;
  relation: string;
  object: string;
  user: string;
  context: {
    is_on_vacation?: boolean;
  };
  reason: string;
  requested_scopes?: string[];
}

interface Props {
  checks: FGACheck[];
  isLoading?: boolean;
}

export default function FGAExplanationCard({ checks, isLoading }: Props) {
  // Only show if there are FGA checks with actual decisions
  const relevantChecks = checks.filter(c => c.relation !== 'n/a');

  if (relevantChecks.length === 0 && !isLoading) {
    return null;
  }

  const allowed = relevantChecks.filter(c => c.allowed);
  const denied = relevantChecks.filter(c => !c.allowed);

  return (
    <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3 border-b border-neutral-border">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Shield className="w-5 h-5" />
          Fine-Grained Authorization (FGA)
        </h3>
        <p className="text-white/80 text-xs mt-1">
          Okta + Auth0 FGA Better Together
        </p>
      </div>

      <div className="p-4 space-y-4">
        {/* Explainer */}
        <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-3 border border-purple-100">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-purple-600 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-purple-800">
              <strong>Why FGA?</strong> Okta handles identity and group-based access.
              FGA adds <em>contextual</em> conditions evaluated at runtime - like blocking
              access when a manager is on vacation.
            </div>
          </div>
        </div>

        {/* Model Visualization */}
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
          <div className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1">
            <Database className="w-3.5 h-3.5" />
            FGA Authorization Model
          </div>
          <div className="font-mono text-[10px] text-gray-700 bg-white rounded p-2 border overflow-x-auto">
            <div className="text-purple-600">type inventory_system</div>
            <div className="ml-2 text-gray-500">relations</div>
            <div className="ml-4">
              <span className="text-blue-600">manager</span>: [user <span className="text-orange-600">with check_vacation</span>]
            </div>
            <div className="ml-4">
              <span className="text-blue-600">can_increase_inventory</span>: manager
            </div>
            <div className="mt-2 text-orange-600">condition check_vacation(is_on_vacation: bool)</div>
            <div className="ml-2 text-gray-600">is_on_vacation == <span className="text-red-600">false</span></div>
          </div>
        </div>

        {/* Summary */}
        {relevantChecks.length > 0 && (
          <div className="flex items-center gap-4 pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-success-green/10 flex items-center justify-center">
                <CheckCircle className="w-4 h-4 text-success-green" />
              </div>
              <div>
                <div className="text-lg font-bold text-success-green">{allowed.length}</div>
                <div className="text-[10px] text-gray-500 uppercase">Allowed</div>
              </div>
            </div>

            {denied.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-error-red/10 flex items-center justify-center">
                  <XCircle className="w-4 h-4 text-error-red" />
                </div>
                <div>
                  <div className="text-lg font-bold text-error-red">{denied.length}</div>
                  <div className="text-[10px] text-gray-500 uppercase">Denied</div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Check Details */}
        <div className="space-y-2">
          {relevantChecks.map((check, idx) => (
            <div
              key={idx}
              className={`rounded-lg border-2 p-3 transition-all ${
                check.allowed
                  ? 'border-success-green/30 bg-success-green/5'
                  : 'border-error-red/30 bg-error-red/5'
              }`}
            >
              {/* Check Flow Visualization */}
              <div className="flex items-center gap-2 text-xs mb-2">
                <div className="flex items-center gap-1 px-2 py-1 bg-white rounded border">
                  <User className="w-3 h-3 text-gray-500" />
                  <span className="font-mono text-gray-700">{check.user.replace('user:', '')}</span>
                </div>
                <ArrowRight className="w-3 h-3 text-gray-400" />
                <div className={`px-2 py-1 rounded font-mono ${
                  check.allowed ? 'bg-success-green/20 text-success-green' : 'bg-error-red/20 text-error-red'
                }`}>
                  {check.relation}
                </div>
                <ArrowRight className="w-3 h-3 text-gray-400" />
                <div className="flex items-center gap-1 px-2 py-1 bg-white rounded border">
                  <Database className="w-3 h-3 text-gray-500" />
                  <span className="font-mono text-gray-700">{check.object}</span>
                </div>
              </div>

              {/* Vacation Context */}
              {check.context?.is_on_vacation !== undefined && (
                <div className={`flex items-center gap-2 text-xs mb-2 px-2 py-1.5 rounded ${
                  check.context.is_on_vacation
                    ? 'bg-orange-50 border border-orange-200'
                    : 'bg-green-50 border border-green-200'
                }`}>
                  <Palmtree className={`w-3.5 h-3.5 ${
                    check.context.is_on_vacation ? 'text-orange-500' : 'text-green-500'
                  }`} />
                  <span className={check.context.is_on_vacation ? 'text-orange-700' : 'text-green-700'}>
                    is_on_vacation = <strong>{check.context.is_on_vacation ? 'true' : 'false'}</strong>
                  </span>
                  {check.context.is_on_vacation && (
                    <span className="text-orange-600 font-medium ml-auto">
                      Condition FAILED
                    </span>
                  )}
                </div>
              )}

              {/* Result */}
              <div className={`flex items-center gap-2 ${
                check.allowed ? 'text-success-green' : 'text-error-red'
              }`}>
                {check.allowed ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <XCircle className="w-4 h-4" />
                )}
                <span className="text-sm font-medium">
                  {check.allowed ? 'Access Allowed' : 'Access Denied'}
                </span>
              </div>

              {/* Reason */}
              <div className="mt-2 text-xs text-gray-600 bg-white rounded p-2 border">
                {check.reason}
              </div>

              {/* Requested Scopes */}
              {check.requested_scopes && check.requested_scopes.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {check.requested_scopes.map((scope, sIdx) => (
                    <span
                      key={sIdx}
                      className={`px-2 py-0.5 text-[10px] rounded-full font-mono border ${
                        check.allowed
                          ? 'bg-success-green/10 text-success-green border-success-green/30'
                          : 'bg-error-red/10 text-error-red border-error-red/30 line-through'
                      }`}
                    >
                      {scope}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Loading State */}
        {isLoading && relevantChecks.length === 0 && (
          <div className="text-center py-4 text-gray-400">
            <Shield className="w-6 h-6 mx-auto mb-2 animate-pulse" />
            <p className="text-xs">Checking FGA permissions...</p>
          </div>
        )}

        {/* Footer: Better Together Message */}
        <div className="pt-3 border-t border-gray-100">
          <div className="flex items-center gap-3 text-[10px] text-gray-500">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-okta-blue"></div>
              <span>Okta: Identity + RBAC</span>
            </div>
            <span>+</span>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-purple-600"></div>
              <span>FGA: Fine-Grained + Contextual</span>
            </div>
            <span>=</span>
            <span className="font-semibold text-gray-700">Complete Governance</span>
          </div>
        </div>
      </div>
    </div>
  );
}
