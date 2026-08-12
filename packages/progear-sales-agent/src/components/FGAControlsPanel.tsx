'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { BadgeCheck, Briefcase, Loader2, PauseCircle, Plane, PlayCircle, RotateCcw, ShieldAlert } from 'lucide-react';
import { API_BASE_URL } from '@/lib/config';
import { getOrCreateFGADemoSessionId, useFGASimulation } from '@/hooks/useFGASimulation';

interface Props {
  onApplied?: () => void;
}

interface DemoStatus {
  clearance_level: number;
  is_a_manager: boolean;
  is_on_vacation: boolean;
}

const ROLES = [
  { level: 0, name: 'Sales', summary: 'Read inventory. Ask a manager to make changes.' },
  { level: 1, name: 'Manager', summary: 'Make inventory changes up to 600 units.' },
  { level: 2, name: 'VP', summary: 'Make inventory changes of any size.' },
] as const;

const roleForLevel = (level: number) => ROLES.find((role) => role.level === level);

export default function FGAControlsPanel({ onApplied }: Props) {
  const { data: session } = useSession();
  const { isEnabled, setIsEnabled } = useFGASimulation();
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [roleLevel, setRoleLevel] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const idToken = session?.idToken;

  const demoHeaders = useCallback((includeJson = false) => ({
    ...(includeJson ? { 'Content-Type': 'application/json' } : {}),
    Authorization: `Bearer ${idToken}`,
    'X-Demo-Session-ID': getOrCreateFGADemoSessionId(),
  }), [idToken]);

  const loadStatus = useCallback(async () => {
    if (!idToken || !isEnabled) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/demo-status`, {
        headers: demoHeaders(),
      });
      if (!response.ok) return;
      const data: DemoStatus = await response.json();
      setStatus(data);
      setRoleLevel(data.clearance_level ?? 0);
    } catch {
      // The controls remain usable after the next successful status refresh.
    }
  }, [demoHeaders, idToken, isEnabled]);

  useEffect(() => {
    if (isEnabled) {
      void loadStatus();
    } else {
      setStatus(null);
      setLastResult(null);
    }
  }, [isEnabled, loadStatus]);

  async function callToggle(attribute: 'clearance_level' | 'is_on_vacation', value: number | boolean) {
    if (!idToken) return;
    setBusy(attribute);
    setLastResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/demo-toggle`, {
        method: 'POST',
        headers: demoHeaders(true),
        body: JSON.stringify({ attribute, value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Update failed');
      const values: DemoStatus | undefined = data.values;
      if (values) {
        setStatus(values);
        setRoleLevel(values.clearance_level ?? 0);
      } else {
        setStatus((previous) => (previous ? { ...previous, [attribute]: data.value } : previous));
      }
      const message = attribute === 'clearance_level'
        ? `Role changed to Level ${data.value} — ${roleForLevel(data.value)?.name ?? 'Unknown'}. Manager is ${data.values?.is_a_manager ? 'True' : 'False'}.`
        : `On vacation is now ${data.value ? 'True' : 'False'}.`;
      setLastResult(`${message} The next FGA prompt in this browser session uses this value.`);
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
        headers: demoHeaders(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Reset failed');
      await loadStatus();
      setLastResult('Restored this browser session’s starting role and vacation state. Demo personas return to On vacation False.');
      onApplied?.();
    } catch (error) {
      setLastResult(`Error: ${error instanceof Error ? error.message : 'Reset failed'}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="overflow-hidden rounded-xl border-2 border-purple-200 bg-white shadow-sm dark:border-purple-900 dark:bg-slate-900">
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3">
        <h2 className="flex items-center gap-2 font-semibold text-white">
          <ShieldAlert className="h-5 w-5" />
          FGA Demo Controls
        </h2>
        <p className="mt-1 text-xs text-white/80">
          Isolated to this browser session{session?.user?.email ? ` — ${session.user.email}` : ''}
        </p>
      </div>

      <div className="space-y-5 p-4">
        <div className="rounded-xl border border-purple-200 bg-purple-50/70 p-4 dark:border-purple-800 dark:bg-purple-950/30">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
                {isEnabled ? <PauseCircle className="h-5 w-5 text-purple-600 dark:text-purple-300" /> : <PlayCircle className="h-5 w-5 text-purple-600 dark:text-purple-300" />}
                Simulate FGA
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                  isEnabled
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}>
                  {isEnabled ? 'On' : 'Off by default'}
                </span>
              </div>
              <p className="mt-1 max-w-xl text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                Turn this on for the role, quantity threshold, and VP approval demo. It also reveals the guided FGA prompts on the chat page.
                <span className="mt-1 block font-medium text-purple-700 dark:text-purple-300">
                  Other engineers using the same account are not affected. Signing out turns the simulation off.
                </span>
                <span className="mt-1 block text-slate-500 dark:text-slate-400">
                  Production uses the live Okta profile. These controls overlay only the hosted demo decision; signed tokens still show the live Okta claims.
                </span>
              </p>
            </div>
            <button
              type="button"
              aria-pressed={isEnabled}
              onClick={() => setIsEnabled(!isEnabled)}
              className={`shrink-0 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                isEnabled
                  ? 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700'
                  : 'bg-purple-600 text-white shadow-sm hover:bg-purple-700'
              }`}
            >
              {isEnabled ? 'Stop simulation' : 'Simulate FGA'}
            </button>
          </div>
        </div>

        {isEnabled ? (
          <>
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-800 dark:text-slate-100">
            <BadgeCheck className="h-4 w-4 text-blue-600" />
            Role level
            {status ? (
              <span className="text-xs font-normal text-gray-500 dark:text-slate-400">
                Current: {status.clearance_level} — {roleForLevel(status.clearance_level)?.name}
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
                      ? 'border-blue-500 bg-blue-50 shadow-sm dark:bg-blue-950/40'
                      : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-gray-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-blue-700 dark:hover:bg-slate-800'
                  }`}
                >
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">
                    {role.level} — {role.name}
                  </div>
                  <div className="mt-1 text-[11px] leading-relaxed text-gray-600 dark:text-slate-300">{role.summary}</div>
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => callToggle('clearance_level', roleLevel)}
            disabled={busy !== null || status?.clearance_level === roleLevel}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-300 dark:hover:bg-blue-900/60"
          >
            {busy === 'clearance_level' ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Apply role level
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/70">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
              <Briefcase className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
              Manager
              <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                status?.is_a_manager
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
              }`}>
                {status?.is_a_manager ? 'True' : 'False'}
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
              Derived from role: Sales is False; Manager and VP are True. This session keeps the two values synchronized.
            </p>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 dark:border-amber-900 dark:bg-amber-950/25">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
              <Plane className="h-4 w-4 text-amber-600 dark:text-amber-300" />
              On vacation
              <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                status?.is_on_vacation
                  ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
                  : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
              }`}>
                {status?.is_on_vacation ? 'True' : 'False'}
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
              True suspends agent delegation before ID-JAG for every resource. False is the default and allows normal policy checks to continue.
            </p>
            <p className="mt-2 text-[11px] font-medium leading-relaxed text-amber-800 dark:text-amber-200">
              Demo overlay only. In production, the live Okta attribute remains admin- or lifecycle-managed—not an employee self-service setting.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {[true, false].map((value) => (
                <button
                  key={String(value)}
                  type="button"
                  aria-pressed={status?.is_on_vacation === value}
                  onClick={() => callToggle('is_on_vacation', value)}
                  disabled={busy !== null || status?.is_on_vacation === value}
                  className={`rounded-lg border px-3 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                    status?.is_on_vacation === value
                      ? value
                        ? 'border-red-300 bg-red-100 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
                        : 'border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                      : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800'
                  }`}
                >
                  {busy === 'is_on_vacation' && status?.is_on_vacation !== value
                    ? <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                    : value ? 'True' : 'False'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={callReset}
          disabled={busy !== null}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {busy === 'reset' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
          Reset this demo session
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
          </>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-3 text-center text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
            Role controls are hidden until you choose <strong>Simulate FGA</strong>.
          </p>
        )}
      </div>
    </section>
  );
}
