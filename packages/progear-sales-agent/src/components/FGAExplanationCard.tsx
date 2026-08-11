'use client';

import { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Clock3, Shield, XCircle } from 'lucide-react';
import FGAArchitectureDiagram from '@/components/FGAArchitectureDiagram';

interface FGACheck {
  agent: string;
  allowed: boolean;
  direct_allowed?: boolean;
  request_allowed?: boolean;
  relation: string;
  reason: string;
  user_claims?: {
    clearance_level: number;
    role_name?: string;
  };
  policy?: {
    operation: 'read' | 'write';
    quantity?: number | null;
    required_level: number;
    required_role: string;
    approval_required: boolean;
    approval_level?: number | null;
    approval_role?: string | null;
    hard_denial_reason?: string | null;
  };
}

interface Props {
  checks: FGACheck[];
  isLoading?: boolean;
}

const ROLE_ROWS = [
  { level: '0 — Sales', read: 'Yes', standard: 'Contact manager', large: 'Contact manager' },
  { level: '1 — Manager', read: 'Yes', standard: 'Execute', large: 'VP approval' },
  { level: '2 — VP', read: 'Yes', standard: 'Execute', large: 'Execute' },
] as const;

export default function FGAExplanationCard({ checks, isLoading = false }: Props) {
  const [isExpanded, setIsExpanded] = useState(true);
  const latest = [...checks].reverse().find((check) => check.agent === 'inventory');
  const policy = latest?.policy;
  const claims = latest?.user_claims;

  let resultLabel = 'No inventory check yet';
  let ResultIcon = Clock3;
  let resultClass = 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200';
  if (latest) {
    if (policy?.hard_denial_reason) {
      resultLabel = policy.hard_denial_reason;
      ResultIcon = XCircle;
      resultClass = 'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200';
    } else if (policy?.approval_required) {
      resultLabel = `${policy.approval_role} approval required`;
      ResultIcon = Clock3;
      resultClass = 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200';
    } else if (latest.allowed) {
      resultLabel = 'Allowed to execute';
      ResultIcon = CheckCircle2;
      resultClass = 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200';
    } else {
      resultLabel = latest.reason;
      ResultIcon = XCircle;
      resultClass = 'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200';
    }
  } else if (isLoading) {
    resultLabel = 'Checking FGA…';
  }

  return (
    <section className="overflow-hidden rounded-xl border-2 border-purple-200 bg-white shadow-sm dark:border-purple-900 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setIsExpanded((value) => !value)}
        aria-expanded={isExpanded}
        className="flex w-full items-center justify-between bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3 text-left transition hover:brightness-110"
      >
        <div>
          <h2 className="flex items-center gap-2 font-semibold text-white">
            <Shield className="h-5 w-5" />
            Fine-Grained Authorization (FGA) Architecture
          </h2>
          <p className="mt-1 text-xs text-white/80">One Okta role level. One live FGA decision.</p>
        </div>
        {isExpanded ? <ChevronUp className="h-5 w-5 text-white" /> : <ChevronDown className="h-5 w-5 text-white" />}
      </button>

      {isExpanded ? (
        <div className="space-y-5 p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-900 dark:bg-blue-950/40">
              <div className="text-xs font-bold uppercase tracking-wide text-blue-700">1. Okta</div>
              <p className="mt-1 text-xs leading-relaxed text-blue-900 dark:text-blue-100">
                Signs the user’s role level into the inventory token.
              </p>
            </div>
            <div className="rounded-lg border border-purple-200 bg-purple-50 p-3 dark:border-purple-900 dark:bg-purple-950/40">
              <div className="text-xs font-bold uppercase tracking-wide text-purple-700">2. FGA</div>
              <p className="mt-1 text-xs leading-relaxed text-purple-900 dark:text-purple-100">
                Combines the signed role with the action and quantity on every request.
              </p>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/40">
              <div className="text-xs font-bold uppercase tracking-wide text-amber-700">3. Okta OIG</div>
              <p className="mt-1 text-xs leading-relaxed text-amber-900 dark:text-amber-100">
                Collects VP approval when a Manager requests more than 600 units.
              </p>
            </div>
          </div>

          <FGAArchitectureDiagram />

          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">The whole policy</h3>
            <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">Standard means 1–600 units. Large means 601 or more.</p>
            <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-600 dark:bg-slate-800 dark:text-slate-300">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Role level</th>
                    <th className="px-3 py-2 font-semibold">Read</th>
                    <th className="px-3 py-2 font-semibold">Write 1–600 units</th>
                    <th className="px-3 py-2 font-semibold">Write 601+ units</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
                  {ROLE_ROWS.map((row) => (
                    <tr key={row.level}>
                      <th className="whitespace-nowrap px-3 py-2 font-semibold text-gray-900 dark:text-white">{row.level}</th>
                      <td className="px-3 py-2 text-gray-700 dark:text-slate-300">{row.read}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-slate-300">{row.standard}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-slate-300">{row.large}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-gray-500 dark:text-slate-400">
              Sales is always read-only. Only a Manager crossing 600 units creates an approval request.
            </p>
          </div>

          <div className={`rounded-lg border p-3 ${resultClass}`}>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <ResultIcon className="h-4 w-4" />
              Latest decision: {resultLabel}
            </div>
            {latest && claims ? (
              <p className="mt-1 text-xs">
                Okta sent Level {claims.clearance_level} — {claims.role_name ?? 'Unknown'} · FGA checked <code>{latest.relation}</code>
                {policy?.quantity ? ` for ${policy.quantity.toLocaleString()} units` : ''}.
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
