import type { SavedRecord } from '@/types/operator';
import { issueButton } from './issueForms';
import { revisionUtc } from './revisionUtc';
export function TransportDecisionList({
  records,
  disabled,
  onCorrect,
  onHistory,
  onAction,
}: {
  records: SavedRecord[];
  disabled: boolean;
  onCorrect: (r: SavedRecord) => void;
  onHistory: (id: string) => void;
  onAction: (r: SavedRecord) => void;
}) {
  return (
    <ol className="space-y-3">
      {records.map(
        (r) =>
          r.payload.entry_type === 'transport_decision' && (
            <li
              key={r.record_id}
              className="min-w-0 space-y-2 rounded-lg border p-3 [overflow-wrap:anywhere]"
            >
              <h3 className="font-semibold">
                {r.payload.title}
                {r.deleted ? ' · Removed' : ''}
              </h3>
              {r.payload.services.map((s) => (
                <div key={s.row_id}>
                  <p>
                    {s.service}
                    {s.intended ? ` · Intended ${s.intended.transport}` : ''}
                    {s.requested ? ` · Requested ${s.requested.transport}` : ''}
                    {s.applied
                      ? ` · Reported Applied ${s.applied.transport}`
                      : ''}
                    {s.checked
                      ? ` · Operator Checked (${s.checked.result.replaceAll('_', ' ')})`
                      : ' · Not checked'}
                  </p>
                  <p className="text-sm">
                    Requested {revisionUtc(s.requested?.time.at ?? null)} ·
                    Applied {revisionUtc(s.applied?.time.at ?? null)} · Checked{' '}
                    {revisionUtc(s.checked?.time.at ?? null)}
                  </p>
                </div>
              ))}
              {r.payload.reason && <p>Reason: {r.payload.reason}</p>}
              {r.payload.note && <p>{r.payload.note}</p>}
              <p className="text-xs">
                {r.scope} {r.leg_id ?? ''} · version {r.version} · Recorded{' '}
                {revisionUtc(r.recorded_at)}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  className={issueButton}
                  disabled={disabled || r.deleted}
                  onClick={() => onCorrect(r)}
                >
                  Correct this decision
                </button>
                <button
                  className={issueButton}
                  onClick={() => onHistory(r.record_id)}
                >
                  Decision history
                </button>
                <button
                  className={issueButton}
                  disabled={disabled}
                  onClick={() => onAction(r)}
                >
                  {r.deleted ? 'Restore decision' : 'Remove decision'}
                </button>
              </div>
            </li>
          )
      )}
    </ol>
  );
}
