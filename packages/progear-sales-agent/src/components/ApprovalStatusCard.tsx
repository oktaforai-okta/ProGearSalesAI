'use client';

import { useEffect, useState } from 'react';
import {
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  ShieldAlert,
  User,
  XCircle,
} from 'lucide-react';
import { API_BASE_URL } from '@/lib/config';

type Approver = {
  email?: string | null;
  display_name?: string | null;
};

type Intent = {
  user_email?: string;
  agent?: string;
  scope?: string;
  product_name?: string;
  quantity_delta?: number;
  original_task?: string;
};

type ExecutionResult = {
  txn_id: string;
  previous_quantity: number;
  new_quantity: number;
};

export type ApprovalStatus = {
  request_id: string;
  status: 'pending' | 'approved' | 'executed' | 'denied';
  submitted_at?: string | null;
  approved_at?: string | null;
  executed_at?: string | null;
  approver?: Approver | null;
  intent?: Intent | null;
  execution_result?: ExecutionResult | null;
  denial_reason?: string | null;
  poll_error?: boolean;
  approver_group?: string;
};

interface Props {
  initial: ApprovalStatus;
  onStatusChange?: (status: ApprovalStatus) => void;
}

const STATUS_STYLES: Record<
  ApprovalStatus['status'],
  { badge: string; gradient: string; icon: React.ReactElement }
> = {
  pending: {
    badge: 'bg-amber-100 text-amber-900 border-amber-300',
    gradient: 'from-amber-500 to-orange-500',
    icon: <Clock className="w-5 h-5" />,
  },
  approved: {
    badge: 'bg-blue-100 text-blue-900 border-blue-300',
    gradient: 'from-blue-500 to-indigo-500',
    icon: <ShieldAlert className="w-5 h-5" />,
  },
  executed: {
    badge: 'bg-emerald-100 text-emerald-900 border-emerald-300',
    gradient: 'from-emerald-500 to-teal-500',
    icon: <CheckCircle className="w-5 h-5" />,
  },
  denied: {
    badge: 'bg-rose-100 text-rose-900 border-rose-300',
    gradient: 'from-rose-500 to-red-500',
    icon: <XCircle className="w-5 h-5" />,
  },
};

export default function ApprovalStatusCard({ initial, onStatusChange }: Props) {
  const [status, setStatus] = useState<ApprovalStatus>(initial);
  // Default expanded so the user sees the live transition on first render.
  const [isExpanded, setIsExpanded] = useState(true);

  useEffect(() => {
    // Stop polling once the request reaches a terminal state.
    if (status.status === 'executed' || status.status === 'denied') {
      return;
    }
    const id = status.request_id;
    let cancelled = false;

    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/approvals/${id}`);
        if (!res.ok) return;
        const data: ApprovalStatus = await res.json();
        if (cancelled) return;
        if (data.status !== status.status) {
          onStatusChange?.(data);
        }
        setStatus(data);
      } catch {
        /* swallow — next tick will retry */
      }
    };

    tick();
    const handle = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [status.request_id, status.status]);

  const style = STATUS_STYLES[status.status];
  const intent = status.intent ?? {};

  return (
    <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full bg-gradient-to-r ${style.gradient} px-4 py-3 border-b border-neutral-border flex items-center justify-between hover:brightness-110 transition text-left`}
      >
        <div>
          <h3 className="text-white font-semibold flex items-center gap-2">
            {style.icon}
            Approval Request
          </h3>
          <p className="text-white/80 text-xs mt-1">
            OIG Access Request · {status.status.toUpperCase()}
            {status.poll_error ? ' · retrying' : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${style.badge}`}
          >
            {status.status}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-white" />
          ) : (
            <ChevronDown className="w-5 h-5 text-white" />
          )}
        </div>
      </button>

      {/* Body */}
      {isExpanded && (
        <div className="p-4 space-y-3 text-sm">
          <div className="text-xs text-gray-500">
            Request ID:{' '}
            <span className="font-mono text-gray-700">
              {status.request_id}
            </span>
          </div>

          {intent.original_task && (
            <div>
              <span className="text-gray-500">Task:</span>{' '}
              <span className="italic">
                &ldquo;{intent.original_task}&rdquo;
              </span>
            </div>
          )}

          {typeof intent.quantity_delta === 'number' &&
            intent.product_name && (
              <div>
                <span className="text-gray-500">Action:</span> add{' '}
                {intent.quantity_delta.toLocaleString()}{' '}
                {intent.product_name}
                {intent.scope ? (
                  <span className="text-gray-500"> · {intent.scope}</span>
                ) : null}
              </div>
            )}

          {status.approver_group && (
            <div>
              <span className="text-gray-500">Approver group:</span>{' '}
              <span className="font-medium">{status.approver_group}</span>
            </div>
          )}

          {status.submitted_at && (
            <div>
              <span className="text-gray-500">Submitted:</span>{' '}
              {status.submitted_at}
            </div>
          )}

          {status.approved_at && (
            <div className="flex items-center gap-1">
              <User className="w-4 h-4 text-blue-600" />
              <span className="text-gray-500">Approved:</span>{' '}
              {status.approved_at}
              {status.approver?.display_name ? (
                <span> by {status.approver.display_name}</span>
              ) : null}
            </div>
          )}

          {status.status === 'executed' && status.execution_result && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
              <div className="flex items-center gap-2 text-emerald-800 font-medium">
                <CheckCircle className="w-4 h-4" />
                Executed
              </div>
              <div className="mt-1 text-gray-700">
                Transaction:{' '}
                <span className="font-mono text-xs">
                  {status.execution_result.txn_id}
                </span>
              </div>
              {status.execution_result.previous_quantity >= 0 &&
                status.execution_result.new_quantity >= 0 && (
                  <div className="text-gray-700">
                    Quantity:{' '}
                    {status.execution_result.previous_quantity.toLocaleString()}{' '}
                    →{' '}
                    {status.execution_result.new_quantity.toLocaleString()}
                  </div>
                )}
            </div>
          )}

          {status.status === 'denied' && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3">
              <div className="flex items-center gap-2 text-rose-800 font-medium">
                <XCircle className="w-4 h-4" />
                Denied
              </div>
              {status.denial_reason && (
                <div className="mt-1 text-gray-700">
                  {status.denial_reason}
                </div>
              )}
            </div>
          )}

          {(status.status === 'pending' || status.status === 'approved') && (
            <div className="text-xs text-gray-500 italic">
              Polling every 5 seconds. Safe to close the tab — the backend
              will still complete this request once approval lands.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
