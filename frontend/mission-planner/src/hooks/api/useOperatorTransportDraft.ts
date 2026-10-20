import { useState } from 'react';
import type { TransportDraft } from '@/types/operatorTransport';

export const transportDraftPrefix = 'operator-369-draft:';
export const transportDraftKey = (
  identity: string,
  missionId: string,
  recordId = 'new'
) => `${transportDraftPrefix}${identity}:${missionId}:${recordId}`;

export function useOperatorTransportDraft(
  key: string,
  initial: TransportDraft
) {
  function load() {
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw)
        return { key, draft: initial, storageError: null as string | null };
      const value = JSON.parse(raw) as TransportDraft;
      if (
        value.input?.record_type !== 'transport_decision' ||
        !Array.isArray(value.input.payload?.services) ||
        !Array.isArray(value.replacement_check_row_ids)
      )
        throw new Error('Invalid draft');
      return { key, draft: value, storageError: null as string | null };
    } catch {
      return {
        key,
        draft: initial,
        storageError:
          'Draft storage unavailable or invalid. Keep this page open.',
      };
    }
  }
  const [state, setState] = useState(load);
  if (state.key !== key) setState(load());
  function setDraft(draft: TransportDraft) {
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
