'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { BadgeCheck, Loader2, Palmtree, RotateCcw, ShieldAlert } from 'lucide-react';
import { API_BASE_URL } from '@/lib/config';

interface Props {
  onApplied?: () => void;
}

interface DemoStatus {
  is_on_vacation: boolean;
  clearance_level: number;
}

const ROLES = [
  { level: 1, name: 'Sales', summary: 'Read inventory and submit change requests.' },
  { level: 2, name: 'Manager', summary: 'Make inventory changes up to 600 units.' },
  { level: 3, name: 'VP', summary: 'Make inventory changes of any size.' },
] as const;

export default function FGAControlsPanel({ onApplied }: Props) {
  const { data: session } = useSession();
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [roleLevel, setRoleLevel] = useState(1);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const idToken = session?.idToken;

  const loadStatus = useCallback(async () => {
    if (!idToken) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/demo-status`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!response.ok) return;
      const data: DemoStatus = await response.json();
      setStatus(data);
      setRoleLevel(data.clearance_level ?? 1);
    } catch {
      // The controls remain usable after the next successful status refresh.
    }
  }, [idToken]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  async function callToggle(attribute: 'is_on_vacation' | 'clearance_level', value: boolean | number) {
    if (!idToken) return;
    setBusy(attribute);
    setLastResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/demo-toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${idToken}` },
        body: JSON.stringify({ attribute, value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Update failed');
      setStatus((previous) => (previous ? { ...previous, [attribute]: data.value } : previous));
      const message =
        attribute === 'clearance_level'
          ? `Role changed to Level ${data.value} — ${ROLES[data.value - 1]?.name ?? 'Unknown'}.`
          : `On vacation is now ${data.value ? 'True' : 'False'}.`;
      setLastResult(`${message} The next prompt uses the new Okta value.`);
      onApplied?.();
    } catch (error) {
      setLastResult(`Error: ${error instanceof Error ? error.message : 'Update failed'}`);
    } finally {
      setBusy(null);
    }
  }

  async function callReset() {
    if (!idToken) return;
    setBusy('reset');
    setLastResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/demo-reset`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Reset failed');
      await loadStatus();
      setLastResult('Restored this persona’s starting role and set On vacation to False.');
      onApplied?.();
    } catch (error) {
      setLastResult(`Error: ${error instanceof Error ? error.message : 'Reset failed'}`);
    } finally {
      setBusy(null);
    }
  }

  const vacationButtonClass = (active: boolean, trueButton: boolean) => {
    if (active) {
      return trueButton
        ? 'rounded-lg border-2 border-orange-500 bg-orange-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm disabled:opacity-50'
        : 'rounded-lg border-2 border-emerald-600 bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm disabled:opacity-50';
    }
    return 'rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-50 disabled:opacity-50';
  };

  return (
    <section className="overflow-hidden rounded-xl border-2 border-purple-200 bg-white shadow-sm">
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3">
        <h2 className="flex items-center gap-2 font-semibold text-white">
          <ShieldAlert className="h-5 w-5" />
          FGA Demo Controls
        </h2>
        <p className="mt-1 text-xs text-white/80">
          Changes your live Okta profile{session?.user?.email ? ` — ${session.user.email}` : ''}
        </p>
      </div>

      <div className="space-y-5 p-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-800">
            <BadgeCheck className="h-4 w-4 text-blue-600" />
            Role level
            {status ? (
              <span className="text-xs font-normal text-gray-500">
                Current: {status.clearance_level} — {ROLES[status.clearance_level - 1]?.name}
              </span>
            ) : null}
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {ROLES.map((role) => {
              const active = roleLevel === role.level;
              return (
                <button
                  key={role.level}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setRoleLevel(role.level)}
                  disabled={busy !== null}
                  className={`rounded-lg border-2 p-3 text-left transition disabled:opacity-50 ${
                    active
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="text-sm font-semibold text-gray-900">
                    {role.level} — {role.name}
                  </div>
                  <div className="mt-1 text-[11px] leading-relaxed text-gray-600">{role.summary}</div>
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => callToggle('clearance_level', roleLevel)}
            disabled={busy !== null || status?.clearance_level === roleLevel}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === 'clearance_level' ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Apply role level
          </button>
        </div>

        <div className="flex items-center justify-between border-t border-gray-100 pt-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
              <Palmtree className="h-4 w-4 text-orange-500" />
              On vacation
            </div>
            <p className="mt-1 text-[11px] text-gray-500">False is the default. True blocks inventory writes.</p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              aria-pressed={status?.is_on_vacation === true}
              onClick={() => callToggle('is_on_vacation', true)}
              disabled={busy !== null}
              className={vacationButtonClass(status?.is_on_vacation === true, true)}
            >
              True
            </button>
            <button
              type="button"
              aria-pressed={status?.is_on_vacation === false}
              onClick={() => callToggle('is_on_vacation', false)}
              disabled={busy !== null}
              className={vacationButtonClass(status?.is_on_vacation === false, false)}
            >
              False
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={callReset}
          disabled={busy !== null}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
        >
          {busy === 'reset' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
          Reset my demo attributes
        </button>

        {lastResult ? (
          <div
            role="status"
            className={`rounded-lg border p-2 text-xs ${
              lastResult.startsWith('Error')
                ? 'border-red-200 bg-red-50 text-red-700'
                : 'border-green-200 bg-green-50 text-green-700'
            }`}
          >
            {lastResult}
          </div>
        ) : null}
      </div>
    </section>
  );
}
