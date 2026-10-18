import { useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  useOperatorHealth,
  operatorIdentity,
} from '@/hooks/api/operatorReadSession';
import type {
  CallInput,
  ConferenceInput,
  JournalInput,
  OperatorInput,
  Scope,
} from '@/types/operator';
import { JournalEditor } from '../JournalEditor';
import { CallEditor } from '../CallEditor';
import { ConferenceEditor } from '../ConferenceEditor';
import { useOperatorWorkspace } from './OperatorWorkspaceProvider';
import { commandLane, targetIdentity } from './commandRegistry';

export interface EditorMission {
  id: string;
  name: string;
  legs: { id: string; name: string }[];
}

export function WorkspaceEditor({
  mission,
  onReturnFocus,
}: {
  mission?: EditorMission;
  onReturnFocus?: () => void;
}) {
  const workspace = useOperatorWorkspace();
  const draft = workspace.selectedDraftId
    ? workspace.registry.resumeDraft(workspace.selectedDraftId)
    : null;
  const health = useOperatorHealth(false);
  const returnFocus = useRef<HTMLElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!draft) return null;
  const tray = workspace.tray.find(
    (row) => row.lane === commandLane(draft.target)
  );
  const wrongStore =
    operatorIdentity(health.data) !== targetIdentity(draft.target);
  const unavailable = health.isError || !health.data?.ready;
  const saveDisabled =
    unavailable || wrongStore || !!tray?.pending || tray?.status === 'saving';
  const legs = mission?.id === draft.target.missionId ? mission.legs : [];
  function update(input: OperatorInput) {
    if (!draft) return;
    workspace.registry.parkDraft({
      ...draft,
      input,
      revision: draft.revision + 1,
      target: {
        ...draft.target,
        scope: input.scope,
        legId: input.leg_id,
        previousLegId: input.payload.previous_leg_id,
        nextLegId: input.payload.next_leg_id,
      },
    });
    workspace.refreshDrafts();
  }
  function editorState(patch: Record<string, unknown>) {
    if (!draft) return;
    workspace.registry.parkDraft({
      ...draft,
      revision: draft.revision + 1,
      editorState: { ...draft.editorState, ...patch },
    });
    workspace.refreshDrafts();
  }
  function association(patch: {
    previous_leg_id?: string | null;
    next_leg_id?: string | null;
  }) {
    if (!draft) return;
    // Both fields are common to every payload; preserve the discriminated pair.
    update({
      ...draft.input,
      payload: { ...draft.input.payload, ...patch },
    } as OperatorInput);
  }
  async function saveInput(input: OperatorInput) {
    if (!draft || saveDisabled) return;
    update(input);
    await workspace.submitDraft(draft.draftId);
  }
  function legSelect(
    label: string,
    value: string | null,
    onChange: (value: string | null) => void,
    required = false
  ) {
    return (
      <label>
        {label}
        <select
          className="ws-field"
          value={value ?? ''}
          required={required}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">
            {required ? 'Choose a leg' : 'Unknown / none'}
          </option>
          {value && !legs.some((leg) => leg.id === value) && (
            <option value={value}>Unresolved leg · {value}</option>
          )}
          {legs.map((leg) => (
            <option key={leg.id} value={leg.id}>
              {leg.name}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) workspace.closeEditor();
      }}
    >
      <DialogContent
        className="ws-editor"
        onOpenAutoFocus={() => {
          returnFocus.current = document.activeElement as HTMLElement | null;
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus.current?.isConnected) returnFocus.current.focus();
          else onReturnFocus?.();
        }}
      >
        <div className="ws-editor-heading">
          <DialogTitle>
            {draft.target.recordId ? 'Edit' : 'Create'}{' '}
            {draft.input.payload.entry_type.replaceAll('_', ' ')}
          </DialogTitle>
          <button className="ws-button" onClick={() => workspace.closeEditor()}>
            Keep draft and return
          </button>
        </div>
        <DialogDescription>
          Draft mission:{' '}
          {mission?.id === draft.target.missionId
            ? mission.name
            : draft.target.missionId}{' '}
          · Times are UTC. Reports record operator actions.
        </DialogDescription>
        <div className="ws-editor-body">
          {(draft.persistence.message || error) && (
            <p role="alert">{error ?? draft.persistence.message}</p>
          )}
          {unavailable && (
            <p role="status">
              Store unavailable. Keep editing your retained input; saving
              requires a ready store.
            </p>
          )}
          {wrongStore && (
            <p role="alert">
              This draft targets a different store or source. Reread and
              reconcile before saving.
            </p>
          )}
          {tray && (
            <div role="status">
              <p>
                {tray.status.replaceAll('_', ' ')} · {tray.title}
              </p>
              {tray.message && <p>{tray.message}</p>}
              {(tray.status === 'needs_review' ||
                tray.status === 'quarantined' ||
                tray.status === 'accepted_unreadable') && (
                <button
                  className="ws-button"
                  onClick={() =>
                    void workspace.rereadAndReconcile(tray.commandId)
                  }
                >
                  Reread and reconcile
                </button>
              )}
              {tray.current && tray.current.version !== draft.baseVersion && (
                <button
                  className="ws-button"
                  onClick={() => {
                    workspace.registry.parkDraft({
                      ...draft,
                      baseRecord: tray.current!,
                      baseVersion: tray.current!.version,
                      revision: draft.revision + 1,
                    });
                    workspace.refreshDrafts();
                  }}
                >
                  Keep my input using current version {tray.current.version} as
                  base
                </button>
              )}
            </div>
          )}
          <div className="ws-draft-context">
            <label>
              Draft scope
              <select
                className="ws-field"
                value={draft.input.scope}
                onChange={(event) =>
                  update({
                    ...draft.input,
                    scope: event.target.value as Scope,
                    leg_id:
                      event.target.value === 'leg'
                        ? (draft.input.leg_id ?? '')
                        : null,
                  })
                }
              >
                <option value="mission">Mission</option>
                <option value="preflight">Preflight</option>
                <option value="leg">Leg</option>
                <option value="between_legs">Between legs</option>
                <option value="postflight">Postflight</option>
              </select>
            </label>
            {draft.input.scope === 'leg' &&
              legSelect(
                'Leg',
                draft.input.leg_id,
                (leg_id) => update({ ...draft.input, leg_id }),
                true
              )}
            {draft.input.scope === 'between_legs' && (
              <>
                {legSelect(
                  'Previous leg',
                  draft.input.payload.previous_leg_id,
                  (previous_leg_id) => association({ previous_leg_id })
                )}
                {legSelect(
                  'Next leg',
                  draft.input.payload.next_leg_id,
                  (next_leg_id) => association({ next_leg_id })
                )}
              </>
            )}
          </div>
          {draft.input.record_type === 'call' ? (
            <CallEditor
              key={draft.draftId}
              draft={draft.input as CallInput}
              creating={!draft.target.recordId}
              disabled={false}
              saveDisabled={saveDisabled}
              onChange={update}
              onSubmit={(value) => void saveInput(value)}
            />
          ) : draft.input.record_type === 'conference' ? (
            <ConferenceEditor
              draft={draft.input as ConferenceInput}
              disabled={saveDisabled}
              onChange={update}
              onSubmit={(value) => void saveInput(value)}
            />
          ) : draft.input.record_type === 'journal_entry' &&
            ['note', 'call_observation'].includes(
              draft.input.payload.entry_type
            ) ? (
            <JournalEditor
              key={`${draft.draftId}:${draft.baseVersion}`}
              missionId={draft.target.missionId}
              record={draft.baseRecord ?? undefined}
              draft={draft.input as JournalInput}
              contextual
              disabled={false}
              saveDisabled={saveDisabled}
              onChange={update}
              auditNote={String(draft.editorState?.auditNote ?? '')}
              onAuditNoteChange={(auditNote) => editorState({ auditNote })}
              onSave={(command) => {
                if (!saveDisabled)
                  void workspace.submitDraft(draft.draftId, { command });
              }}
            />
          ) : (
            <p>
              This retained draft uses its operational editor. Keep it parked
              while opening the matching view.
            </p>
          )}
          <button
            className="ws-button ws-destructive"
            onClick={() => {
              const result = workspace.registry.discardDraft(draft.draftId);
              if (result.state === 'durable') workspace.closeEditor();
              else setError(result.message);
              workspace.refreshDrafts();
            }}
          >
            Discard draft
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
