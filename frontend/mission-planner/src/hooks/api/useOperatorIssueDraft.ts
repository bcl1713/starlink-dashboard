import { useState } from 'react';
export interface DraftIdentity {
  storeId: string;
  epoch: string;
  sourceMode: string;
  simulationRunId: string | null;
  missionId: string;
  recordId: string;
}
export const issueDraftKey = (identity: DraftIdentity) =>
  'operator-367-draft:' + JSON.stringify(identity);
export function useOperatorIssueDraft<T>(identity: DraftIdentity, initial: T) {
  const key = issueDraftKey(identity);
  const [state, setState] = useState<{
    key: string;
    draft: T;
    storageError: string | null;
  }>(() => {
    try {
      const raw = sessionStorage.getItem(key);
      return {
        key,
        draft: raw ? (JSON.parse(raw) as T) : initial,
        storageError: null,
      };
    } catch {
      return {
        key,
        draft: initial,
        storageError: 'Draft storage unavailable. Keep this page open.',
      };
    }
  });
  // Store-bound editors remount on identity changes; never leak a previous draft.
  if (state.key !== key) {
    let draft = initial;
    let storageError = null;
    try {
      const raw = sessionStorage.getItem(key);
      if (raw) draft = JSON.parse(raw) as T;
    } catch {
      storageError = 'Draft storage unavailable. Keep this page open.';
    }
    setState({ key, draft, storageError });
  }
  function setDraft(draft: T) {
    let storageError = null;
    try {
      sessionStorage.setItem(key, JSON.stringify(draft));
    } catch {
      storageError =
        'Draft could not be retained across reload. Keep this page open.';
    }
    setState({ key, draft, storageError });
  }
  function clear() {
    try {
      sessionStorage.removeItem(key);
      setState({ key, draft: initial, storageError: null });
    } catch {
      setState({
        ...state,
        storageError: 'Stored draft could not be cleared.',
      });
    }
  }
  return {
    draft: state.key === key ? state.draft : initial,
    setDraft,
    clear,
    storageError: state.storageError,
  };
}
