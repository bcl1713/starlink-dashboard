import { capabilityInput } from './capabilityInput';
import type {
  CapabilityInput,
  CapabilityPayload,
  SavedRecord,
} from '@/types/operator';
import {
  useOperatorIssueDraft,
  type DraftIdentity,
} from '@/hooks/api/useOperatorIssueDraft';
import {
  instant,
  issueButton,
  issueField,
  utcValue,
  parseUtc,
} from './issueForms';
export interface CapabilityEditorDraft {
  input: CapabilityInput;
  version: number | null;
  currentDimensions: ('functional' | 'redundancy')[];
}
export function CapabilityEditor({
  missionId,
  record,
  identity,
  disabled,
  asOf,
  onSave,
}: {
  missionId: string;
  record?: SavedRecord;
  identity: DraftIdentity;
  disabled: boolean;
  asOf: string | null;
  onSave: (
    input: CapabilityInput,
    version: number | null,
    currentDimensions: ('functional' | 'redundancy')[]
  ) => Promise<boolean>;
}) {
  const initial = capabilityInput(missionId, record);
  const { draft, setDraft, clear, storageError } = useOperatorIssueDraft(
    identity,
    {
      input: initial,
      version: record?.version ?? null,
      currentDimensions: [] as ('functional' | 'redundancy')[],
    }
  );
  return (
    <CapabilityForm
      draft={draft}
      onDraftChange={setDraft}
      onSaved={clear}
      storageError={storageError}
      record={record}
      disabled={disabled}
      asOf={asOf}
      onSave={onSave}
    />
  );
}
export function CapabilityForm({
  formId,
  draft,
  onDraftChange: setDraft,
  onSaved,
  storageError,
  record,
  disabled,
  saveDisabled = false,
  asOf,
  onSave,
}: {
  formId?: string;
  draft: CapabilityEditorDraft;
  onDraftChange: (draft: CapabilityEditorDraft) => void;
  onSaved?: () => void;
  storageError?: string | null;
  record?: SavedRecord;
  disabled: boolean;
  saveDisabled?: boolean;
  asOf: string | null;
  onSave: (
    input: CapabilityInput,
    version: number | null,
    currentDimensions: ('functional' | 'redundancy')[]
  ) => Promise<boolean>;
}) {
  const input = draft.input;
  const patch = (
    fields: Partial<CapabilityPayload>,
    dimension?: 'functional' | 'redundancy',
    useCurrentTime = false
  ) =>
    setDraft({
      ...draft,
      currentDimensions: dimension
        ? [
            ...(draft.currentDimensions ?? []).filter((d) => d !== dimension),
            ...(useCurrentTime ? [dimension] : []),
          ]
        : (draft.currentDimensions ?? []),
      input: { ...input, payload: { ...input.payload, ...fields } },
    });
  return (
    <form
      id={formId}
      aria-label="Capability assessment"
      className="min-w-0 space-y-3 rounded-lg border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (disabled || saveDisabled) return;
        void onSave(
          { ...input, time: instant(asOf) },
          draft.version,
          draft.currentDimensions ?? []
        ).then((ok) => {
          if (ok) onSaved?.();
        });
      }}
    >
      <fieldset disabled={disabled} className="min-w-0 space-y-3">
        <h3 className="font-semibold">
          {record ? 'Update manual assessment' : 'Record manual assessment'}
        </h3>
        <p>
          Operator reported · functional service and redundancy are independent.
        </p>
        {storageError && <p role="alert">{storageError}</p>}
        <label className="block">
          Capability name
          <input
            className={issueField}
            maxLength={200}
            required
            value={input.payload.title}
            onChange={(e) => patch({ title: e.target.value })}
          />
        </label>
        <div className="grid min-w-0 gap-3 sm:grid-cols-2">
          {(['functional', 'redundancy'] as const).map((dimension) => (
            <div key={dimension} className="space-y-2">
              <label className="block">
                {dimension === 'functional'
                  ? 'Functional capability'
                  : 'Redundancy'}
                <select
                  aria-label={
                    dimension === 'functional'
                      ? 'Functional capability'
                      : 'Redundancy'
                  }
                  className={issueField}
                  value={input.payload[`${dimension}_status`]}
                  onChange={(e) =>
                    patch(
                      {
                        [`${dimension}_status`]: e.target.value,
                        [`${dimension}_observed_at`]: null,
                        [`${dimension}_time_precision`]: 'unknown',
                      },
                      dimension,
                      true
                    )
                  }
                >
                  {(dimension === 'functional'
                    ? ['unknown', 'functional', 'degraded', 'unavailable']
                    : ['unknown', 'available', 'degraded', 'unavailable']
                  ).map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label className="flex min-h-11 items-center gap-2">
                <input
                  type="checkbox"
                  checked={(draft.currentDimensions ?? []).includes(dimension)}
                  onChange={(e) => patch({}, dimension, e.target.checked)}
                />
                Use current UTC for {dimension} observation
              </label>
              <label className="block">
                {dimension === 'functional'
                  ? 'Functional observation UTC'
                  : 'Redundancy observation UTC'}
                <input
                  className={issueField}
                  type="datetime-local"
                  step="1"
                  disabled={(draft.currentDimensions ?? []).includes(dimension)}
                  value={utcValue(input.payload[`${dimension}_observed_at`])}
                  onChange={(e) =>
                    patch(
                      {
                        [`${dimension}_observed_at`]: parseUtc(e.target.value),
                        [`${dimension}_time_precision`]: e.target.value
                          ? 'exact'
                          : 'unknown',
                      },
                      dimension,
                      false
                    )
                  }
                />
              </label>
              <label className="block">
                {dimension === 'functional'
                  ? 'Functional time precision'
                  : 'Redundancy time precision'}
                <select
                  aria-label={
                    dimension === 'functional'
                      ? 'Functional time precision'
                      : 'Redundancy time precision'
                  }
                  className={issueField}
                  value={input.payload[`${dimension}_time_precision`]}
                  onChange={(e) =>
                    patch(
                      {
                        [`${dimension}_time_precision`]: e.target.value,
                        ...(e.target.value === 'unknown'
                          ? { [`${dimension}_observed_at`]: null }
                          : {}),
                      },
                      dimension,
                      e.target.value === 'unknown'
                        ? false
                        : (draft.currentDimensions ?? []).includes(dimension)
                    )
                  }
                >
                  {['unknown', 'exact', 'approximate'].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            </div>
          ))}
        </div>
        <label className="block">
          Assessment notes
          <textarea
            aria-label="Assessment notes"
            className={issueField}
            maxLength={8000}
            value={input.payload.note}
            onChange={(e) => patch({ note: e.target.value })}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            hidden={!!formId}
            className={issueButton}
            disabled={saveDisabled}
          >
            Save assessment
          </button>
          <button
            className={issueButton}
            type="button"
            onClick={onSaved}
            hidden={!onSaved}
          >
            Discard assessment draft
          </button>
          {record && draft.version !== record.version && (
            <button
              className={issueButton}
              type="button"
              onClick={() => setDraft({ ...draft, version: record.version })}
            >
              Apply reviewed assessment to current version
            </button>
          )}
        </div>
      </fieldset>
    </form>
  );
}
