'use client';

import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { ShieldAlert, Palmtree, Key as KeyIcon, RotateCcw, Loader2 } from 'lucide-react';
import { API_BASE_URL } from '@/lib/config';

interface Props {
  onApplied?: () => void;
}

interface DemoStatus {
  is_on_vacation: boolean;
  is_a_manager: boolean;
  clearance_level: number;
}

// Mutates the signed-in user's REAL Okta profile via the backend's
// /api/admin/demo-toggle (scoped server-side to the caller's own sub - see
// backend/auth/demo_admin.py). Deliberately not a client-side simulation:
// the point is to remove the "log into Okta Admin Console mid-demo" friction
// while keeping the FGA check genuinely live.
export default function FGAControlsPanel({ onApplied }: Props) {
  const { data: session } = useSession();
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [clearance, setClearance] = useState(5);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const idToken = session?.idToken;

  async function loadStatus() {
    if (!idToken) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/demo-status`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!res.ok) return;
      const data: DemoStatus = await res.json();
      setStatus(data);
      setClearance(data.clearance_level ?? 5);
    } catch {
      // Non-fatal - buttons just fall back to showing nothing selected.
    }
  }

  useEffect(() => {
    loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idToken]);

  async function callToggle(attribute: string, value: unknown) {
    if (!idToken) return;
    setBusy(attribute);
    setLastResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/demo-toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${idToken}` },
        body: JSON.stringify({ attribute, value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Toggle failed');
      setStatus((prev) => (prev ? { ...prev, [attribute]: data.value } : prev));
      setLastResult(`Updated your Okta profile: ${attribute} = ${JSON.stringify(data.value)}. ${data.note || ''}`);
      onApplied?.();
    } catch (err) {
      setLastResult(`Error: ${err instanceof Error ? err.message : 'Toggle failed'}`);
    } finally {
      setBusy(null);
    }
  }

  async function callReset() {
    if (!idToken) return;
    setBusy('reset');
    setLastResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/demo-reset`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Reset failed');
      setLastResult(
        data.reset?.length
          ? `Reset ${data.reset.join(', ')} to their original values.`
          : 'Nothing to reset - no attributes have been toggled yet.'
      );
      await loadStatus();
      onApplied?.();
    } catch (err) {
      setLastResult(`Error: ${err instanceof Error ? err.message : 'Reset failed'}`);
    } finally {
      setBusy(null);
    }
  }

  // Active state gets a solid, filled style; inactive gets a plain outline -
  // so it's obvious at a glance which value is actually live right now,
  // not just which button happens to be styled "colored".
  function toggleButtonClass(isActive: boolean, color: 'orange' | 'green') {
    if (isActive) {
      return color === 'orange'
        ? 'px-3 py-1.5 text-xs rounded-lg border-2 border-orange-500 bg-orange-500 text-white font-semibold shadow-sm disabled:opacity-50 flex items-center gap-1'
        : 'px-3 py-1.5 text-xs rounded-lg border-2 border-green-600 bg-green-600 text-white font-semibold shadow-sm disabled:opacity-50 flex items-center gap-1';
    }
    return 'px-3 py-1.5 text-xs rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-gray-500 disabled:opacity-50 flex items-center gap-1';
  }

  return (
    <div className="bg-white rounded-xl border-2 border-purple-200 shadow-sm overflow-hidden">
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <ShieldAlert className="w-5 h-5" />
          Fine-Grained Demo Controls
        </h3>
        <p className="text-white/80 text-xs mt-1">
          Changes your real Okta profile{session?.user?.email ? ` - ${session.user.email}` : ''}
        </p>
      </div>

      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <Palmtree className="w-4 h-4 text-orange-500" />
            On vacation
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => callToggle('is_on_vacation', true)}
              disabled={busy !== null}
              className={toggleButtonClass(status?.is_on_vacation === true, 'orange')}
            >
              {busy === 'is_on_vacation' && <Loader2 className="w-3 h-3 animate-spin" />}
              Set true
            </button>
            <button
              onClick={() => callToggle('is_on_vacation', false)}
              disabled={busy !== null}
              className={toggleButtonClass(status?.is_on_vacation === false, 'orange')}
            >
              Set false
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <ShieldAlert className="w-4 h-4 text-green-600" />
            Manager
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => callToggle('is_a_manager', true)}
              disabled={busy !== null}
              className={toggleButtonClass(status?.is_a_manager === true, 'green')}
            >
              {busy === 'is_a_manager' && <Loader2 className="w-3 h-3 animate-spin" />}
              Set true
            </button>
            <button
              onClick={() => callToggle('is_a_manager', false)}
              disabled={busy !== null}
              className={toggleButtonClass(status?.is_a_manager === false, 'green')}
            >
              Set false
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <KeyIcon className="w-4 h-4 text-blue-600" />
            Clearance level
            {status && (
              <span className="text-[10px] text-gray-400">(current: {status.clearance_level})</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={clearance}
              onChange={(e) => setClearance(Number(e.target.value))}
              className="text-xs border border-gray-300 rounded-lg px-2 py-1.5"
            >
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <button
              onClick={() => callToggle('clearance_level', clearance)}
              disabled={busy !== null}
              className="px-3 py-1.5 text-xs rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 disabled:opacity-50"
            >
              Apply
            </button>
          </div>
        </div>

        <button
          onClick={callReset}
          disabled={busy !== null}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-300 bg-gray-50 hover:bg-gray-100 text-gray-700 disabled:opacity-50"
        >
          <RotateCcw className="w-4 h-4" />
          Reset my demo attributes
        </button>

        {lastResult && (
          <div
            className={`text-xs p-2 rounded-lg border ${
              lastResult.startsWith('Error')
                ? 'bg-red-50 text-red-700 border-red-200'
                : 'bg-green-50 text-green-700 border-green-200'
            }`}
          >
            {lastResult}
          </div>
        )}
      </div>
    </div>
  );
}
