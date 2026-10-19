import apiClient from '@/services/api-client';
import type { OperatorHealth } from '@/types/operator';
import type { Mission } from '@/types/mission';
import type { TrainingIdentity } from './trainingProgress';
import { trainingContext } from './trainingContext';
import { sameJson } from './trainingRecordIdentity';

/** Private client exercise only: no sender, fake receipt or backend fault endpoint. */
export async function armPrivateReceiptLoss(
  identity: TrainingIdentity,
  signal: AbortSignal,
  finished: (reason: 'withheld' | 'expired') => void
) {
  const admission = new AbortController();
  const abortAdmission = () => admission.abort();
  signal.addEventListener('abort', abortAdmission, { once: true });
  const bound = setTimeout(abortAdmission, 3000);
  try {
    if (signal.aborted) throw new Error('Private exercise canceled.');
    const [health, mission] = await Promise.all([
      apiClient.get<OperatorHealth>('/api/v2/operator/health', {
        signal: admission.signal,
      }),
      apiClient.get<Mission>(
        '/api/v2/missions/' + encodeURIComponent(identity.missionId),
        { signal: admission.signal }
      ),
    ]);
    const context = trainingContext(health.data, mission.data, identity.origin);
    if (
      !context ||
      !sameJson(context.identity, identity) ||
      (globalThis.location && globalThis.location.origin !== identity.origin)
    )
      throw new Error(
        'Receipt exercise requires the current marked private training store.'
      );
  } finally {
    clearTimeout(bound);
    signal.removeEventListener('abort', abortAdmission);
    admission.abort();
  }
  if (signal.aborted) throw new Error('Private exercise canceled.');
  let active = true;
  function disarm() {
    if (!active) return;
    active = false;
    apiClient.interceptors.response.eject(interceptor);
    clearTimeout(expiration);
    signal.removeEventListener('abort', disarm);
  }
  const interceptor = apiClient.interceptors.response.use((response) => {
    if (!active || signal.aborted) return response;
    const config = response.config;
    if (
      config.method?.toLowerCase() !== 'post' ||
      config.url !== '/api/v2/operator/records' ||
      config.headers.get('X-Operator-Store-Epoch') !== identity.epoch ||
      !config.headers.get('Idempotency-Key')
    )
      return response;
    let body;
    try {
      body =
        typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
    } catch {
      return response;
    }
    if (
      body?.mission_id !== identity.missionId ||
      body.record_type !== 'journal_entry' ||
      body.payload?.entry_type !== 'note'
    )
      return response;
    disarm();
    finished('withheld');
    // The normal HTTP save already returned successfully. Deliberately do not
    // hand its response to the journal owner or retain it as guide evidence.
    throw new Error(
      'Private training exercise withheld this note receipt. Retain the original request and check saved history before recovery.'
    );
  });
  signal.addEventListener('abort', disarm, { once: true });
  const expiration = setTimeout(() => {
    disarm();
    finished('expired');
  }, 60_000);
}
