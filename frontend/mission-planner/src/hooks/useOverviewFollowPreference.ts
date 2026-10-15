import { useSyncExternalStore } from 'react';
const key = 'overview.follow-aircraft';
const changed = 'overview-follow-preference-change';
function snapshot() {
  try {
    return window.localStorage.getItem(key) === 'true';
  } catch {
    return false;
  }
}
function subscribe(notify: () => void) {
  window.addEventListener('storage', notify);
  window.addEventListener(changed, notify);
  return () => {
    window.removeEventListener('storage', notify);
    window.removeEventListener(changed, notify);
  };
}
export function setOverviewFollowPreference(enabled: boolean) {
  try {
    window.localStorage.setItem(key, String(enabled));
    window.dispatchEvent(new Event(changed));
    return true;
  } catch {
    return false;
  }
}
export function useOverviewFollowPreference() {
  return useSyncExternalStore(subscribe, snapshot, () => false);
}
