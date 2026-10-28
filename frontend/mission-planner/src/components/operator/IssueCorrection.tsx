import { UtcDateTime } from './UtcDateTime';
import type { SavedRecord, OperatorCommand } from '@/types/operator';
import {
  useOperatorIssueDraft,
  type DraftIdentity,
} from '@/hooks/api/useOperatorIssueDraft';
import { issueInput, issueButton, issueField } from './issueForms';
export function IssueCorrection({
  current,
  target,
  identity,
  disabled,
  onSave,
  onClose,
}: {
  current: SavedRecord;
  target: SavedRecord;
  identity: DraftIdentity;
  disabled: boolean;
  onSave: (command: OperatorCommand) => Promise<boolean>;
  onClose: () => void;
}) {
  const { draft, setDraft, clear, storageError } = useOperatorIssueDraft(
    {
      ...identity,
      recordId: current.record_id + ':correction:' + target.version,
    },
    {
      input: issueInput(current.mission_id, current),
      version: current.version,
      text:
        target.payload.entry_type === 'issue'
          ? (target.payload.update_text ?? '')
          : '',
      at:
        target.payload.entry_type === 'issue' && target.payload.corrects_version
          ? (target.payload.corrected_update_at ?? null)
          : target.time.occurred_at,
    }
  );
  return (
    <form
      aria-label="Correct historical update"
      className="space-y-3 rounded border p-3"
      onSubmit={(e) => {
        e.preventDefault();
        void onSave({
          operation: 'update',
          record_id: current.record_id,
          body: {
            ...draft.input,
            expected_version: draft.version,
            payload: {
              ...draft.input.payload,
              update_text: draft.text,
              corrects_version: target.version,
              corrected_update_at: draft.at,
            },
          },
        }).then((ok) => {
          if (ok) {
            clear();
            onClose();
          }
        });
      }}
    >
      <fieldset disabled={disabled} className="space-y-3">
        <p>
          Correct historical update · current status and follow-up are
          preserved.
        </p>
        {storageError && <p role="alert">{storageError}</p>}
        <label className="block">
          Corrected update
          <textarea
            aria-label="Corrected update"
            className={issueField}
            required
            maxLength={8000}
            value={draft.text}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })}
          />
        </label>
        <UtcDateTime
          label="Corrected occurred"
          value={draft.at}
          onChange={(value) =>
            setDraft({
              ...draft,
              at: value ? new Date(value).toISOString() : null,
            })
          }
        />
        <button className={issueButton}>Save correction</button>
        <button type="button" className={issueButton} onClick={onClose}>
          Close correction
        </button>
        {draft.version !== current.version && (
          <button
            type="button"
            className={issueButton}
            onClick={() =>
              setDraft({
                ...draft,
                input: issueInput(current.mission_id, current),
                version: current.version,
              })
            }
          >
            Preserve current state for reviewed correction
          </button>
        )}
      </fieldset>
    </form>
  );
}
