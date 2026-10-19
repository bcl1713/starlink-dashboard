import { useState } from 'react';
import type { TrainingIdentity } from './trainingProgress';
import {
  decodeRecoveryObservation,
  type RecoveryObservation,
} from './trainingRecoveryEvidence';

export function TrainingRecoveryFile({
  identity,
  checking,
  retained,
  onCheck,
}: {
  identity: TrainingIdentity;
  checking: boolean;
  retained?: RecoveryObservation;
  onCheck: (value: RecoveryObservation) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  return (
    <fieldset
      className="min-w-0 space-y-3 rounded border p-3 [overflow-wrap:anywhere]"
      disabled={checking || reading}
    >
      <legend>Private recovery evidence</legend>
      <p>
        Use the native backup/restore warmup before the first flight, then
        select its evidence JSON in the restored store. This checks tooling
        facts against current saved history. Old-epoch guide progress stays
        separate.
      </p>
      <label>
        Native recovery report
        <input
          className="ws-field"
          type="file"
          accept=".json,application/json"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setError(null);
            setReading(true);
            try {
              if (file.size > 4 * 1024 * 1024)
                throw new Error(
                  'Select a private recovery JSON report up to 4 MiB.'
                );
              await onCheck(
                decodeRecoveryObservation(
                  JSON.parse(await file.text()),
                  identity
                )
              );
            } catch (reason) {
              setError(
                reason instanceof Error
                  ? reason.message
                  : 'Could not read the recovery report.'
              );
            } finally {
              setReading(false);
            }
          }}
        />
      </label>
      {retained && (
        <p>
          Native restore report retained for this epoch; Check current evidence
          revalidates it.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
    </fieldset>
  );
}
