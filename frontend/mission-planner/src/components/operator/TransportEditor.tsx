import { useState } from 'react';
import type { OperatorCommand, SavedRecord, Scope } from '@/types/operator';
import {
  transportDraftKey,
  useOperatorTransportDraft,
} from '@/hooks/api/useOperatorTransportDraft';
import {
  newServiceRow,
  newTransportDraft,
  toTransportCommand,
} from './transportForms';
import { TransportServiceRow } from './TransportServiceRow';
import { issueButton, issueField, parseUtc, utcValue } from './issueForms';

export function TransportEditor({
  missionId,
  record,
  identity,
  disabled,
  createFromDraft = false,
  onSave,
}: {
  missionId: string;
  record?: SavedRecord;
  identity: string;
  disabled: boolean;
  createFromDraft?: boolean;
  onSave: (command: OperatorCommand, draftKey: string) => Promise<boolean>;
}) {
  const key = transportDraftKey(identity, missionId, record?.record_id);
  const { draft, setDraft, clear, storageError } = useOperatorTransportDraft(
    key,
    newTransportDraft(missionId, record)
  );
  const [error, setError] = useState<string>();
  const input = draft.input;
  const rows = input.payload.services;
  function field(patch: Partial<typeof input.payload>) {
    setDraft({
      ...draft,
      input: { ...input, payload: { ...input.payload, ...patch } },
    });
  }
  return (
    <form
      aria-label="Transport decision editor"
      className="min-w-0 space-y-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(undefined);
        try {
          if (
            await onSave(
              toTransportCommand(draft, createFromDraft ? undefined : record),
              key
            )
          )
            clear();
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Unable to save decision.');
        }
      }}
    >
      <h3 className="font-semibold">
        {record && !createFromDraft
          ? 'Correct this decision'
          : 'Record transport decision'}
      </h3>
      <fieldset disabled={disabled} className="min-w-0 space-y-3">
        {rows.map((row, index) => (
          <TransportServiceRow
            key={row.row_id}
            row={row}
            index={index}
            onChange={(value) => {
              setDraft({
                ...draft,
                replacement_check_row_ids: value.checked
                  ? draft.replacement_check_row_ids
                  : draft.replacement_check_row_ids.filter(
                      (id) => id !== row.row_id
                    ),
                input: {
                  ...input,
                  payload: {
                    ...input.payload,
                    services: rows.map((r) =>
                      r.row_id === row.row_id ? value : r
                    ),
                  },
                },
              });
            }}
            onCheck={(value) =>
              setDraft({
                ...draft,
                replacement_check_row_ids: [
                  ...new Set([
                    ...draft.replacement_check_row_ids.filter(
                      (id) => id !== row.row_id
                    ),
                    ...(value.checked ? [row.row_id] : []),
                  ]),
                ],
                input: {
                  ...input,
                  payload: {
                    ...input.payload,
                    services: rows.map((r) =>
                      r.row_id === row.row_id ? value : r
                    ),
                  },
                },
              })
            }
            onRemove={() =>
              setDraft({
                ...draft,
                replacement_check_row_ids:
                  draft.replacement_check_row_ids.filter(
                    (id) => id !== row.row_id
                  ),
                input: {
                  ...input,
                  payload: {
                    ...input.payload,
                    services: rows.filter((r) => r.row_id !== row.row_id),
                  },
                },
              })
            }
          />
        ))}
        <button
          type="button"
          className={issueButton}
          disabled={rows.length >= 32}
          onClick={() => field({ services: [...rows, newServiceRow()] })}
        >
          Add service
        </button>
        <details>
          <summary className="min-h-11 cursor-pointer py-3">
            Reason, timing and associations (optional)
          </summary>
          <div className="space-y-3">
            <label>
              Reason
              <input
                className={issueField}
                maxLength={1000}
                value={input.payload.reason}
                onChange={(e) => field({ reason: e.target.value })}
              />
            </label>
            <label>
              Notes
              <textarea
                className={issueField}
                maxLength={8000}
                value={input.payload.note}
                onChange={(e) => field({ note: e.target.value })}
              />
            </label>
            <label>
              Decision mission
              <input
                className={issueField}
                value={input.mission_id}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    input: { ...input, mission_id: e.target.value },
                  })
                }
              />
            </label>
            <label>
              Decision scope
              <select
                className={issueField}
                value={input.scope}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    input: {
                      ...input,
                      scope: e.target.value as Scope,
                      leg_id: null,
                    },
                  })
                }
              >
                {[
                  'mission',
                  'preflight',
                  'leg',
                  'between_legs',
                  'postflight',
                ].map((s) => (
                  <option key={s} value={s}>
                    {s.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
            {input.scope === 'leg' && (
              <label>
                Decision leg ID
                <input
                  className={issueField}
                  value={input.leg_id ?? ''}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      input: { ...input, leg_id: e.target.value || null },
                    })
                  }
                />
              </label>
            )}
            {(['planned_start_at', 'planned_end_at'] as const).map(
              (name, index) => (
                <label key={name}>
                  Planned change {index ? 'end' : 'start'} UTC
                  <input
                    className={issueField}
                    type="datetime-local"
                    step="1"
                    value={utcValue(input.time[name])}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        input: {
                          ...input,
                          time: {
                            ...input.time,
                            [name]: parseUtc(e.target.value),
                          },
                        },
                      })
                    }
                  />
                </label>
              )
            )}
            <label>
              Related call ID
              <input
                className={issueField}
                value={input.payload.call_id ?? ''}
                onChange={(e) => field({ call_id: e.target.value || null })}
              />
            </label>
            <label>
              Related conference ID
              <input
                className={issueField}
                value={input.payload.conference_id ?? ''}
                onChange={(e) =>
                  field({ conference_id: e.target.value || null })
                }
              />
            </label>
            <p className="text-sm">
              Clear relationships explicitly before moving to another mission or
              removing a linked target. Historical references remain.
            </p>
          </div>
        </details>
        <button
          className={`${issueButton} bg-primary text-primary-foreground`}
          type="submit"
        >
          Save transport decision
        </button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {storageError && <p role="alert">{storageError}</p>}
    </form>
  );
}
