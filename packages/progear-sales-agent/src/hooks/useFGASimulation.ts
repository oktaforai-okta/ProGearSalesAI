'use client';

import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'progear-fga-simulation-v2';
const SESSION_ID_KEY = 'progear-fga-demo-session-v1';
const CHANGE_EVENT = 'progear:fga-simulation-change';
let volatileSessionId: string | null = null;

export function getOrCreateFGADemoSessionId(): string {
  if (typeof window === 'undefined') return '';
  try {
    const existing = window.sessionStorage.getItem(SESSION_ID_KEY);
    if (existing) return existing;

    const sessionId = window.crypto?.randomUUID?.()
      ?? `demo-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.sessionStorage.setItem(SESSION_ID_KEY, sessionId);
    return sessionId;
  } catch {
    if (!volatileSessionId) {
      volatileSessionId = `demo-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
    return volatileSessionId;
  }
}

export function clearFGASimulationPreference() {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
    window.sessionStorage.removeItem(SESSION_ID_KEY);
  } catch {
    // A fresh sign-in still defaults to simple mode when storage is unavailable.
  }
  volatileSessionId = null;
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function readSimulationPreference(): boolean {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function useFGASimulation() {
  const [isEnabled, setIsEnabled] = useState(false);

  useEffect(() => {
    const syncPreference = () => setIsEnabled(readSimulationPreference());
    syncPreference();
    window.addEventListener(CHANGE_EVENT, syncPreference);
    return () => {
      window.removeEventListener(CHANGE_EVENT, syncPreference);
    };
  }, []);

  const updateSimulation = useCallback((enabled: boolean) => {
    try {
      if (enabled) {
        getOrCreateFGADemoSessionId();
        window.sessionStorage.setItem(STORAGE_KEY, 'true');
      } else {
        window.sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // The current page still updates when browser storage is unavailable.
    }
    setIsEnabled(enabled);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  return { isEnabled, setIsEnabled: updateSimulation };
}
