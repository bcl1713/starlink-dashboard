import type {
  IssueInput,
  OperatorCommand,
  SavedRecord,
  Scope,
} from '@/types/operator';
import type { DraftIdentity } from '@/hooks/api/useOperatorIssueDraft';
import { useOperatorIssueDraft } from '@/hooks/api/useOperatorIssueDraft';
import {
  instant,
  issueButton,
  issueField,
  issueInput,
  parseUtc,
  utcValue,
} from './issueForms';
export interface IssueEditorDraft {
  input: IssueInput;
  baseVersion: number | null;
  occurredAt: string | null;
  useCurrentTime: boolean;
}
export function IssueEditor({
  missionId,
  record,
  identity,
  disabled,
  asOf,
  onSave,
  related,
}: {
  missionId: string;
  record?: SavedRecord;
  identity: DraftIdentity;
  disabled: boolean;
  asOf: string | null;
  onSave: (
    command: OperatorCommand,
    useCurrentTime: boolean
  ) => Promise<boolean>;
  related: SavedRecord[];
}) {
  const initial = {
    input: issueInput(missionId, record),
    baseVersion: record?.version ?? null,
    occurredAt: null as string | null,
    useCurrentTime: true,
  };
  const { draft, setDraft, clear, storageError } = useOperatorIssueDraft(
    identity,
    initial
  );
  return (
    <IssueForm
      draft={draft}
      onDraftChange={setDraft}
      onSaved={clear}
      storageError={storageError}
      record={record}
      disabled={disabled}
      asOf={asOf}
      onSave={onSave}
      related={related}
    />
  );
}

export function IssueForm({
  draft,
  onDraftChange: setDraft,
  onSaved,
  storageError,
  record,
  disabled,
  saveDisabled = false,
  asOf,
  onSave,
  related,
  contextual = false,
}: {
  draft: IssueEditorDraft;
  onDraftChange: (draft: IssueEditorDraft) => void;
  onSaved?: () => void;
  storageError?: string | null;
  record?: SavedRecord;
  disabled: boolean;
  saveDisabled?: boolean;
  asOf: string | null;
  onSave: (
    command: OperatorCommand,
    useCurrentTime: boolean
  ) => Promise<boolean>;
  related: SavedRecord[];
  contextual?: boolean;
}) {
  const input = draft.input;
  const patch = (fields: Partial<IssueInput['payload']>) =>
    setDraft({
      ...draft,
      input: { ...input, payload: { ...input.payload, ...fields } },
    });
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (disabled || saveDisabled) return;
    const body = { ...input, time: instant(draft.occurredAt) };
    const command: OperatorCommand =
      draft.baseVersion && record
        ? {
            operation: 'update',
            record_id: record.record_id,
            body: { ...body, expected_version: draft.baseVersion },
          }
        : { operation: 'create', body };
    if (await onSave(command, draft.useCurrentTime ?? true)) onSaved?.();
  }
  return (
    <form
      aria-label="Issue editor"
      onSubmit={(event) => void submit(event)}
      className="min-w-0 space-y-3 rounded-lg border p-4"
    >
      <fieldset disabled={disabled} className="min-w-0 space-y-3">
        <h3 className="font-semibold">
          {record ? 'Update issue' : 'Log a problem'}
        </h3>
        {storageError && <p role="alert">{storageError}</p>}
        <label className="block">
          Problem description
          <input
            className={issueField}
            required
            maxLength={200}
            value={input.payload.title}
            onChange={(e) => patch({ title: e.target.value })}
          />
        </label>
        {record && (
          <label className="block">
            Add update
            <textarea
              aria-label="Add update"
              className={issueField}
              maxLength={8000}
              value={input.payload.update_text ?? ''}
              onChange={(e) => patch({ update_text: e.target.value })}
            />
          </label>
        )}
        <details>
          <summary className="min-h-11 cursor-pointer">
            Optional issue details
          </summary>
          <div className="grid min-w-0 gap-3 sm:grid-cols-2">
            <label>
              Priority
              <select
                aria-label="Priority"
                className={issueField}
                value={input.payload.priority ?? ''}
                onChange={(e) =>
                  patch({
                    priority: (e.target.value ||
                      null) as IssueInput['payload']['priority'],
                  })
                }
              >
                <option value="">Unspecified</option>
                {['low', 'normal', 'high', 'urgent'].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select
                aria-label="Status"
                className={issueField}
                value={input.payload.status}
                onChange={(e) =>
                  patch({
                    status: e.target.value as IssueInput['payload']['status'],
                    ...(e.target.value === 'resolved'
                      ? { follow_up_at: null }
                      : {}),
                  })
                }
              >
                {['open', 'monitoring', 'resolved', 'reopened'].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Mitigation
              <select
                aria-label="Mitigation"
                className={issueField}
                value={input.payload.mitigation ?? 'unknown'}
                onChange={(e) =>
                  patch({
                    mitigation: e.target
                      .value as IssueInput['payload']['mitigation'],
                  })
                }
              >
                {['unknown', 'none_reported', 'mitigated', 'workaround'].map(
                  (v) => (
                    <option key={v}>{v}</option>
                  )
                )}
              </select>
            </label>
            {(['functional_area', 'responsible_party'] as const).map(
              (field) => (
                <label key={field}>
                  {field === 'functional_area'
                    ? 'Functional area'
                    : 'Responsible party (optional)'}
                  <input
                    className={issueField}
                    maxLength={200}
                    value={input.payload[field] ?? ''}
                    onChange={(e) => patch({ [field]: e.target.value || null })}
                  />
                </label>
              )
            )}
            <label>
              Follow-up UTC
              <input
                type="datetime-local"
                step="1"
                className={issueField}
                disabled={input.payload.status === 'resolved'}
                value={utcValue(input.payload.follow_up_at)}
                onChange={(e) =>
                  patch({ follow_up_at: parseUtc(e.target.value) })
                }
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={issueButton}
                disabled={!asOf || input.payload.status === 'resolved'}
                onClick={() =>
                  patch({
                    follow_up_at: new Date(
                      Date.parse(asOf!) + 15 * 60000
                    ).toISOString(),
                  })
                }
              >
                In 15 minutes from snapshot
              </button>
              <button
                type="button"
                className={issueButton}
                onClick={() => patch({ follow_up_at: null })}
              >
                Clear follow-up
              </button>
            </div>
            <label className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                checked={draft.useCurrentTime ?? true}
                onChange={(e) =>
                  setDraft({ ...draft, useCurrentTime: e.target.checked })
                }
              />
              Use current backend UTC when saved
            </label>
            <label>
              Action occurred UTC (optional)
              <input
                type="datetime-local"
                step="1"
                className={issueField}
                disabled={draft.useCurrentTime ?? true}
                value={utcValue(draft.occurredAt)}
                onChange={(e) =>
                  setDraft({ ...draft, occurredAt: parseUtc(e.target.value) })
                }
              />
            </label>
            <label hidden={contextual}>
              Scope
              <select
                aria-label="Scope"
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
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            {input.scope === 'leg' && (
              <label hidden={contextual}>
                Leg ID
                <input
                  className={issueField}
                  required
                  value={input.leg_id ?? ''}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      input: { ...input, leg_id: e.target.value },
                    })
                  }
                />
              </label>
            )}
            {(['capability_id', 'call_id', 'conference_id'] as const).map(
              (field) => {
                const type = {
                  capability_id: 'capability_assessment',
                  call_id: 'call',
                  conference_id: 'conference',
                }[field];
                const choices = related.filter(
                  (r) => !r.deleted && r.payload.entry_type === type
                );
                return (
                  <label key={field}>
                    {field === 'capability_id'
                      ? 'Affected capability'
                      : field === 'call_id'
                        ? 'Related call'
                        : 'Related conference'}
                    <select
                      aria-label={
                        field === 'capability_id'
                          ? 'Affected capability'
                          : field === 'call_id'
                            ? 'Related call'
                            : 'Related conference'
                      }
                      className={issueField}
                      value={input.payload[field] ?? ''}
                      onChange={(e) =>
                        patch({ [field]: e.target.value || null })
                      }
                    >
                      <option value="">None</option>
                      {input.payload[field] &&
                        !choices.some(
                          (r) => r.record_id === input.payload[field]
                        ) && (
                          <option value={input.payload[field]!}>
                            Linked record unavailable
                          </option>
                        )}
                      {choices.map((r) => (
                        <option key={r.record_id} value={r.record_id}>
                          {r.payload.title}
                        </option>
                      ))}
                    </select>
                  </label>
                );
              }
            )}
            <label>
              Relevant transport
              <select
                aria-label="Relevant transport"
                className={issueField}
                value={input.payload.transport ?? ''}
                onChange={(e) =>
                  patch({
                    transport: (e.target.value ||
                      null) as IssueInput['payload']['transport'],
                  })
                }
              >
                <option value="">Unknown / unspecified</option>
                {['Starshield', 'Ka', 'X'].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Notes
              <textarea
                aria-label="Notes"
                className={issueField}
                maxLength={8000}
                value={input.payload.note}
                onChange={(e) => patch({ note: e.target.value })}
              />
            </label>
          </div>
        </details>
        <div className="flex flex-wrap gap-2">
          <button className={issueButton} disabled={disabled || saveDisabled}>
            Save issue
          </button>
          <button
            type="button"
            className={issueButton}
            disabled={disabled}
            onClick={onSaved}
            hidden={!onSaved}
          >
            Discard issue draft
          </button>
          {record && draft.baseVersion !== record.version && (
            <button
              type="button"
              className={issueButton}
              disabled={disabled}
              onClick={() =>
                setDraft({ ...draft, baseVersion: record.version })
              }
            >
              Apply reviewed draft to current version
            </button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Draft retained in this browser tab. Times are UTC. No automatic
          readiness assessment.
        </p>
      </fieldset>
    </form>
  );
}
