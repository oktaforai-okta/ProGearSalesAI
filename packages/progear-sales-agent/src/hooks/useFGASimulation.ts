'use client';

import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'progear-fga-simulation-v1';
const CHANGE_EVENT = 'progear:fga-simulation-change';

export function clearFGASimulationPreference() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // A fresh sign-in still defaults to simple mode when storage is unavailable.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function readSimulationPreference(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function useFGASimulation() {
  const [isEnabled, setIsEnabled] = useState(false);

  useEffect(() => {
    const syncPreference = () => setIsEnabled(readSimulationPreference());
    syncPreference();
    window.addEventListener('storage', syncPreference);
    window.addEventListener(CHANGE_EVENT, syncPreference);
    return () => {
      window.removeEventListener('storage', syncPreference);
      window.removeEventListener(CHANGE_EVENT, syncPreference);
    };
  }, []);

  const updateSimulation = useCallback((enabled: boolean) => {
    try {
      if (enabled) {
        window.localStorage.setItem(STORAGE_KEY, 'true');
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // The current page still updates when browser storage is unavailable.
    }
    setIsEnabled(enabled);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  return { isEnabled, setIsEnabled: updateSimulation };
}
