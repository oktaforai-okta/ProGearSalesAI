'use client';

import { CheckCircle, XCircle, Shield, Palmtree, User, Database, ArrowRight, Info, Key, Package, Link2, UserCheck, Clock } from 'lucide-react';

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
  contextual_tuples?: Array<{ user: string; relation: string; object: string }>;
  user_claims?: {
    is_manager: boolean;
    is_on_vacation: boolean;
    clearance_level: number;
  };
  item_info?: {
    item_id: string;
    required_clearance: number;
  };
  stored_tuples?: {
    manager: string | null;
    clearance: string | null;
  };
}

interface Props {
  checks: FGACheck[];
  isLoading?: boolean;
}

export default function FGAExplanationCard({ checks, isLoading }: Props) {
  // Filter for FGA checks with actual decisions (not pass-through)
  const relevantChecks = checks.filter(c => c.relation !== 'n/a');

  const allowed = relevantChecks.filter(c => c.allowed);
  const denied = relevantChecks.filter(c => !c.allowed);
  const hasChecks = relevantChecks.length > 0;

  // Get user claims from the first check (they're the same for all checks in a request)
  const userClaims = relevantChecks[0]?.user_claims;
  const itemInfo = relevantChecks[0]?.item_info;
  const storedTuples = relevantChecks[0]?.stored_tuples;

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
              FGA adds <em>fine-grained</em> relationship-based checks with contextual conditions
              like vacation status and clearance hierarchies.
            </div>
          </div>
        </div>

        {/* User Claims Section - Real Values from Okta */}
        {userClaims && (
          <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
            <div className="text-xs font-semibold text-blue-700 mb-2 flex items-center gap-1">
              <UserCheck className="w-3.5 h-3.5" />
              User Claims (from Okta Access Token)
            </div>
            <div className="grid grid-cols-2 gap-2">
              {/* Manager Status */}
              <div className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
                userClaims.is_manager
                  ? 'bg-green-100 border border-green-300'
                  : 'bg-red-100 border border-red-300'
              }`}>
                <User className={`w-3.5 h-3.5 ${userClaims.is_manager ? 'text-green-600' : 'text-red-600'}`} />
                <span className={userClaims.is_manager ? 'text-green-700' : 'text-red-700'}>
                  Manager: <strong>{userClaims.is_manager ? 'true' : 'false'}</strong>
                </span>
              </div>

              {/* Vacation Status */}
              <div className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
                userClaims.is_on_vacation
                  ? 'bg-orange-100 border border-orange-300'
                  : 'bg-green-100 border border-green-300'
              }`}>
                <Palmtree className={`w-3.5 h-3.5 ${userClaims.is_on_vacation ? 'text-orange-600' : 'text-green-600'}`} />
                <span className={userClaims.is_on_vacation ? 'text-orange-700' : 'text-green-700'}>
                  Vacation: <strong>{userClaims.is_on_vacation ? 'true' : 'false'}</strong>
                </span>
              </div>

              {/* Clearance Level */}
              <div className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
                itemInfo && userClaims.clearance_level >= itemInfo.required_clearance
                  ? 'bg-green-100 border border-green-300'
                  : 'bg-yellow-100 border border-yellow-300'
              }`}>
                <Key className={`w-3.5 h-3.5 ${
                  itemInfo && userClaims.clearance_level >= itemInfo.required_clearance
                    ? 'text-green-600'
                    : 'text-yellow-600'
                }`} />
                <span className={
                  itemInfo && userClaims.clearance_level >= itemInfo.required_clearance
                    ? 'text-green-700'
                    : 'text-yellow-700'
                }>
                  Clearance: <strong>{userClaims.clearance_level || 0}</strong>
                </span>
              </div>

              {/* Item Required Clearance */}
              {itemInfo && (
                <div className="flex items-center gap-2 px-2 py-1.5 rounded text-xs bg-gray-100 border border-gray-300">
                  <Package className="w-3.5 h-3.5 text-gray-600" />
                  <span className="text-gray-700">
                    Item needs: <strong>{itemInfo.required_clearance}</strong>
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* FGA Model Visualization - Updated to match actual model */}
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
          <div className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1">
            <Database className="w-3.5 h-3.5" />
            FGA Authorization Model (ProGear New)
          </div>
          <div className="font-mono text-[10px] text-gray-700 bg-white rounded p-2 border overflow-x-auto">
            <div className="text-purple-600">type inventory_item</div>
            <div className="ml-2 text-gray-500">relations</div>
            <div className="ml-4">
              <span className="text-blue-600">can_view</span>: <span className="text-gray-600">can_manage from parent</span>
            </div>
            <div className="ml-4">
              <span className="text-blue-600">can_update</span>: <span className="text-orange-600">has_clearance</span> <span className="text-gray-500">and</span> <span className="text-gray-600">can_manage from parent</span>
            </div>
            <div className="mt-2 text-purple-600">type inventory_system</div>
            <div className="ml-2 text-gray-500">relations</div>
            <div className="ml-4">
              <span className="text-blue-600">active_manager</span>: <span className="text-gray-600">manager</span> <span className="text-red-600">but not</span> <span className="text-orange-600">on_vacation</span>
            </div>
          </div>
        </div>

        {/* Tuple Summary */}
        {(storedTuples || relevantChecks[0]?.contextual_tuples) && (
          <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-200">
            <div className="text-xs font-semibold text-indigo-700 mb-2 flex items-center gap-1">
              <Link2 className="w-3.5 h-3.5" />
              FGA Tuples
            </div>
            <div className="space-y-1.5 text-xs">
              {/* Stored Tuples */}
              <div className="flex items-center gap-2">
                <span className="text-indigo-600 font-medium w-16">Stored:</span>
                <div className="flex flex-wrap gap-1">
                  {storedTuples?.manager && (
                    <span className="px-2 py-0.5 bg-white rounded border border-indigo-200 font-mono text-[10px]">
                      manager &rarr; warehouse
                    </span>
                  )}
                  {storedTuples?.clearance && (
                    <span className="px-2 py-0.5 bg-white rounded border border-indigo-200 font-mono text-[10px]">
                      granted_to &rarr; {storedTuples.clearance.replace('clearance_level:', 'level ')}
                    </span>
                  )}
                  {!storedTuples?.manager && !storedTuples?.clearance && (
                    <span className="text-gray-500 italic">none</span>
                  )}
                </div>
              </div>
              {/* Contextual Tuples */}
              <div className="flex items-center gap-2">
                <span className="text-orange-600 font-medium w-16">Context:</span>
                <div className="flex flex-wrap gap-1">
                  {userClaims?.is_on_vacation ? (
                    <span className="px-2 py-0.5 bg-orange-100 rounded border border-orange-300 font-mono text-[10px] text-orange-700">
                      <Clock className="w-3 h-3 inline mr-1" />
                      on_vacation (per-request)
                    </span>
                  ) : (
                    <span className="text-gray-500 italic text-[10px]">none (not on vacation)</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Summary */}
        {hasChecks ? (
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
        ) : !isLoading && (
          <div className="flex items-center gap-3 pb-3 border-b border-gray-100 text-gray-500">
            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
              <Shield className="w-4 h-4 text-gray-400" />
            </div>
            <div className="text-sm">
              No FGA checks performed
              <div className="text-[10px] text-gray-400">FGA applies to inventory operations only</div>
            </div>
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

              {/* Failure Reasons - Show which conditions failed */}
              {!check.allowed && check.user_claims && (
                <div className="space-y-1 mb-2">
                  {check.user_claims.is_on_vacation && (
                    <div className="flex items-center gap-2 text-xs px-2 py-1.5 rounded bg-orange-50 border border-orange-200">
                      <Palmtree className="w-3.5 h-3.5 text-orange-500" />
                      <span className="text-orange-700">
                        <strong>Vacation blocks access</strong> - active_manager requires NOT on_vacation
                      </span>
                      <XCircle className="w-3.5 h-3.5 text-orange-500 ml-auto" />
                    </div>
                  )}
                  {!check.user_claims.is_manager && (
                    <div className="flex items-center gap-2 text-xs px-2 py-1.5 rounded bg-red-50 border border-red-200">
                      <User className="w-3.5 h-3.5 text-red-500" />
                      <span className="text-red-700">
                        <strong>Not a manager</strong> - no manager relationship in FGA
                      </span>
                      <XCircle className="w-3.5 h-3.5 text-red-500 ml-auto" />
                    </div>
                  )}
                  {check.relation === 'can_update' && check.item_info &&
                   check.user_claims.clearance_level < check.item_info.required_clearance && (
                    <div className="flex items-center gap-2 text-xs px-2 py-1.5 rounded bg-yellow-50 border border-yellow-200">
                      <Key className="w-3.5 h-3.5 text-yellow-600" />
                      <span className="text-yellow-700">
                        <strong>Insufficient clearance</strong> - level {check.user_claims.clearance_level} &lt; required {check.item_info.required_clearance}
                      </span>
                      <XCircle className="w-3.5 h-3.5 text-yellow-600 ml-auto" />
                    </div>
                  )}
                </div>
              )}

              {/* Success Reasons */}
              {check.allowed && check.user_claims && (
                <div className="flex items-center gap-2 text-xs px-2 py-1.5 rounded bg-green-50 border border-green-200 mb-2">
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  <span className="text-green-700">
                    {check.relation === 'can_update'
                      ? `Active manager with clearance ${check.user_claims.clearance_level} (item needs ${check.item_info?.required_clearance || '?'})`
                      : 'Active manager (not on vacation)'
                    }
                  </span>
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
