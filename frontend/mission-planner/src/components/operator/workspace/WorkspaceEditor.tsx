import { useEffect, useId, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  useOperatorHealth,
  operatorIdentity,
  sameJournalIdentity,
} from '@/hooks/api/operatorReadSession';
import type {
  CallInput,
  ConferenceInput,
  JournalInput,
  OperatorInput,
  Scope,
  SavedRecord,
} from '@/types/operator';
import { CapabilityForm } from '../CapabilityEditor';
import { TransportForm } from '../TransportEditor';
import { IssueForm } from '../IssueEditor';
import { JournalEditor } from '../JournalEditor';
import { CallEditor, type CallEditorState } from '../CallEditor';
import { ConferenceEditor } from '../ConferenceEditor';
import { conferenceDraft, joinCommand } from '../conferenceCommands';
import { ParticipationEditor } from '../ParticipationEditor';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { readTransportCatalog } from '@/services/transportCatalog';
import { UtcDateTime, type UtcParts } from '../UtcDateTime';
import {
  getOperatorHealth,
  readOperatorRecord,
  readOperatorRecords,
} from '@/services/operator';
import { createEditorDraft } from './editorDraft';
import { useOperatorWorkspace } from './OperatorWorkspaceProvider';
import {
  useMissionAssociation,
  type AssociationMission,
} from '../useMissionAssociation';
import { operationalRelevant } from './operatingContext';
import { commandLane, targetIdentity } from './commandRegistry';

export type EditorMission = AssociationMission;

export function WorkspaceEditor({
  mission,
  onReturnFocus,
}: {
  mission?: EditorMission;
  onReturnFocus?: () => void;
}) {
  const formId = useId();
  const workspace = useOperatorWorkspace();
  const draft = workspace.selectedDraftId
    ? workspace.registry.resumeDraft(workspace.selectedDraftId)
    : null;
  const health = useOperatorHealth(false);
  const inlineParentId =
    typeof draft?.editorState?.inlineParentCallDraftId === 'string'
      ? draft.editorState.inlineParentCallDraftId
      : null;
  const inlineParent = inlineParentId
    ? workspace.registry.resumeDraft(inlineParentId)
    : null;
  const inlineTray = inlineParentId
    ? workspace.tray.find((row) => row.draftId === draft?.draftId)
    : undefined;
  const acceptedReference = draft?.editorState?.inlineConferenceAccepted as
    | { recordId?: unknown; submittedRevision?: unknown }
    | undefined;
  const acceptedRecordId =
    typeof acceptedReference?.recordId === 'string'
      ? acceptedReference.recordId
      : null;
  const [readingInline, setReadingInline] = useState(false);
  const [recoveredConference, setRecoveredConference] = useState<{
    identity: string;
    record: SavedRecord;
  } | null>(null);
  function finishInlineConference(
    saved: SavedRecord,
    submittedRevision: number
  ) {
    if (
      !draft ||
      saved.record_type !== 'conference' ||
      saved.deleted ||
      saved.mission_id !== draft.target.missionId ||
      (inlineParent &&
        (inlineParent.input.record_type !== 'call' ||
          targetIdentity(inlineParent.target) !==
            targetIdentity(draft.target))) ||
      targetIdentity(draft.target) !== operatorIdentity(health.data)
    )
      return;
    function settleInlineDraft() {
      const retained = workspace.registry.resumeDraft(draft!.draftId);
      if (!retained || retained.revision === submittedRevision) {
        workspace.registry.retireSubmitted(draft!.draftId, submittedRevision);
        return;
      }
      // A confirmed create must never replay as another create. Newer input is
      // kept as an ordinary correction against the authoritative saved record.
      const state = { ...retained.editorState };
      delete state.inlineParentCallDraftId;
      delete state.inlineConferenceAccepted;
      workspace.registry.parkDraft({
        ...retained,
        target: {
          ...retained.target,
          recordId: saved.record_id,
          newDraftId: null,
        },
        baseRecord: saved,
        baseVersion: saved.version,
        revision: retained.revision + 1,
        editorState: state,
      });
    }
    if (!inlineParent) {
      settleInlineDraft();
      workspace.closeEditor();
      workspace.refreshDrafts();
      return;
    }
    const retainedParent = workspace.registry.resumeDraft(inlineParent.draftId);
    if (!retainedParent || retainedParent.input.record_type !== 'call') return;
    const parentState = { ...retainedParent.editorState };
    delete parentState.inlineConferenceDraftId;
    workspace.registry.parkDraft({
      ...retainedParent,
      input: {
        ...retainedParent.input,
        payload: {
          ...retainedParent.input.payload,
          conference_id: saved.record_id,
        },
      },
      revision: retainedParent.revision + 1,
      editorState: parentState,
    });
    settleInlineDraft();
    workspace.openDraft(retainedParent.draftId);
    workspace.refreshDrafts();
  }
  useEffect(() => {
    if (
      inlineTray?.status === 'accepted' &&
      inlineTray.receipt &&
      inlineTray.current
    )
      finishInlineConference(inlineTray.current, inlineTray.submittedRevision);
    // Registry revisions and the exact accepted tray row govern this handoff.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, inlineParent, inlineTray, health.data, workspace]);
  const transportCatalog = useQuery({
    queryKey: ['operator-transport-catalog'],
    queryFn: readTransportCatalog,
    retry: false,
    enabled:
      ['call', 'conference'].includes(draft?.input.record_type ?? '') &&
      !!health.data?.ready,
  });
  const usesRelationships = [
    'participation',
    'conference',
    'call',
    'issue',
    'transport_decision',
  ].includes(draft?.input.record_type ?? '');
  const relationships = useInfiniteQuery({
    queryKey: [
      'operator-records',
      draft?.target.missionId,
      operatorIdentity(health.data),
      'workspace-all',
    ],
    queryFn: ({ pageParam }) =>
      readOperatorRecords(
        { mission_id: draft!.target.missionId, include_removed: true },
        pageParam
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    enabled: usesRelationships && !!health.data?.ready,
    retry: false,
  });
  // Share the cockpit snapshot and its authoritative current-record reads.
  // An accepted bridge must not disappear behind a separate relationship query.
  const related = new Map(
    relationships.data?.pages.flatMap((page) =>
      page.items.map((item) => [item.record.record_id, item.record] as const)
    ) ?? []
  );
  for (const row of workspace.confirmedRecords) {
    const record = row.read.record;
    if (
      row.identity !== operatorIdentity(health.data) ||
      record.mission_id !== draft?.target.missionId
    )
      continue;
    const previous = related.get(record.record_id);
    if (!previous || previous.version < record.version)
      related.set(record.record_id, record);
  }
  for (const row of workspace.tray) {
    if (
      row.status === 'accepted' &&
      row.current &&
      targetIdentity(row.target) === operatorIdentity(health.data) &&
      row.current.mission_id === draft?.target.missionId
    ) {
      const previous = related.get(row.current.record_id);
      if (!previous || previous.version < row.current.version)
        related.set(row.current.record_id, row.current);
    }
  }
  if (
    recoveredConference &&
    recoveredConference.identity === operatorIdentity(health.data) &&
    recoveredConference.record.mission_id === draft?.target.missionId
  ) {
    const saved = recoveredConference.record;
    const previous = related.get(saved.record_id);
    if (!previous || previous.version < saved.version)
      related.set(saved.record_id, saved);
  }
  const relatedRecords = [...related.values()].filter((record) =>
    operationalRelevant(record, health.data)
  );
  const timing = useMissionAssociation(
    mission?.id === draft?.target.missionId ? mission : undefined,
    draft?.input.record_type === 'call' ||
      draft?.input.record_type === 'conference'
  );
  const returnFocus = useRef<HTMLElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!draft) return null;
  const saveLabel =
    draft.input.record_type === 'journal_entry'
      ? draft.input.payload.entry_type === 'capability_assessment'
        ? 'Save Assessment'
        : ['note', 'call_observation'].includes(draft.input.payload.entry_type)
          ? 'Save Entry'
          : null
      : draft.input.record_type === 'issue' && draft.target.correctionVersion
        ? 'Save Correction'
        : (
            {
              call: 'Save Call',
              conference: 'Save Conference',
              participation: 'Save Customer Interval',
              transport_decision: 'Save Transport Decision',
              issue: 'Save Issue',
            } as Partial<Record<string, string>>
          )[draft.input.record_type];

  const tray = workspace.tray.find(
    (row) => row.lane === commandLane(draft.target)
  );
  const wrongStore =
    operatorIdentity(health.data) !== targetIdentity(draft.target);
  const unavailable = health.isError || !health.data?.ready;
  const saveDisabled =
    unavailable ||
    wrongStore ||
    !!tray?.pending ||
    tray?.status === 'saving' ||
    (!!inlineParentId && (!!inlineTray?.receipt || !!acceptedRecordId)) ||
    readingInline ||
    workspace.busyLanes.includes(commandLane(draft.target));
  const legs = mission?.id === draft.target.missionId ? mission.legs : [];
  const automatic =
    ['call', 'conference'].includes(draft.input.record_type) &&
    (draft.editorState?.associationMode === 'auto' ||
      (!draft.target.recordId &&
        draft.editorState?.associationMode !== 'manual'));
  const contextualAssociation = ['call', 'conference'].includes(
    draft.input.record_type
  );
  const associationExpanded = draft.editorState?.associationExpanded === true;
  const suggestion = (input: OperatorInput) =>
    input.record_type === 'conference'
      ? timing.current(relationships.data?.pages[0]?.as_of ?? null)
      : timing.at(input.time.planned_start_at);
  const inferred = suggestion(draft.input);
  function associate(input: OperatorInput): OperatorInput {
    if (!automatic) return input;
    const inferred = suggestion(input);
    return {
      ...input,
      scope: inferred?.scope ?? 'mission',
      leg_id: inferred?.leg_id ?? null,
      payload: {
        ...input.payload,
        previous_leg_id: inferred?.previous_leg_id ?? null,
        next_leg_id: inferred?.next_leg_id ?? null,
      },
    } as OperatorInput;
  }
  function update(input: OperatorInput) {
    if (!draft) return;
    input = associate(input);
    const current = workspace.registry.resumeDraft(draft.draftId) ?? draft;
    workspace.registry.parkDraft({
      ...current,
      input,
      revision: current.revision + 1,
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
    const current = workspace.registry.resumeDraft(draft.draftId) ?? draft;
    workspace.registry.parkDraft({
      ...current,
      revision: current.revision + 1,
      editorState: { ...current.editorState, ...patch },
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
    await workspace.submitDraft(
      draft.draftId,
      input.record_type === 'participation' &&
        !draft.target.recordId &&
        input.payload.state === 'connected' &&
        draft.editorState?.joinNow === true &&
        !input.time.occurred_at
        ? {
            atCurrentTime: (now) =>
              joinCommand({ ...input, connect_customer: true }, now),
          }
        : undefined
    );
  }
  function createInlineConference() {
    if (!draft || draft.input.record_type !== 'call' || saveDisabled) return;
    const retained = workspace.registry.resumeDraft(draft.draftId) ?? draft;
    const childId = retained.editorState?.inlineConferenceDraftId;
    if (
      typeof childId === 'string' &&
      workspace.registry.resumeDraft(childId)
    ) {
      workspace.openDraft(childId);
      return;
    }
    const input = conferenceDraft(draft.target.missionId);
    const child = workspace.registry.createDraft(
      {
        ...draft.target,
        recordType: 'conference',
        recordId: null,
        newDraftId: null,
        scope: input.scope,
        legId: input.leg_id,
        previousLegId: input.payload.previous_leg_id,
        nextLegId: input.payload.next_leg_id,
        correctionVersion: null,
      },
      input
    );
    workspace.registry.parkDraft({
      ...child,
      editorState: { inlineParentCallDraftId: draft.draftId },
    });
    workspace.registry.parkDraft({
      ...retained,
      revision: retained.revision + 1,
      editorState: {
        ...retained.editorState,
        inlineConferenceDraftId: child.draftId,
      },
    });
    workspace.openDraft(child.draftId);
    workspace.refreshDrafts();
  }
  function returnToParent() {
    if (inlineParent) workspace.openDraft(inlineParent.draftId);
    else workspace.closeEditor();
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
        if (!open) returnToParent();
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
            {draft.input.payload.entry_type
              .replaceAll('_', ' ')
              .replace(/\b\w/g, (c) => c.toUpperCase())}
          </DialogTitle>
          <button className="ws-button" onClick={returnToParent}>
            {inlineParent ? 'Back To Call' : 'Keep Draft And Return'}
          </button>
        </div>
        <DialogDescription>
          Draft Mission:{' '}
          {mission?.id === draft.target.missionId
            ? mission.name
            : draft.target.missionId}{' '}
          · Times Are Zulu. Reports record operator actions.
        </DialogDescription>
        <div className="ws-editor-body">
          {inlineParentId && (
            <p role="status">
              Your full call draft is parked. This conference is saved
              independently for reuse and selected after its saved state is
              confirmed.
            </p>
          )}
          {inlineParentId && acceptedRecordId && !inlineTray && (
            <div role="status">
              <p>
                Conference save accepted. Reread its saved state to return to
                your call.
              </p>
              <button
                type="button"
                className="ws-button"
                disabled={wrongStore || unavailable || readingInline}
                onClick={async () => {
                  setReadingInline(true);
                  try {
                    const read = await readOperatorRecord(acceptedRecordId);
                    const source = await health.refetch();
                    if (
                      !source.data?.ready ||
                      operatorIdentity(source.data) !==
                        targetIdentity(draft.target)
                    )
                      throw new Error(
                        'Store changed. Keep both drafts and reread after recovery.'
                      );
                    if (
                      read.record.record_id !== acceptedRecordId ||
                      read.record.deleted
                    )
                      throw new Error(
                        'The saved conference is unavailable. Both drafts remain retained.'
                      );
                    setRecoveredConference({
                      identity: targetIdentity(draft.target),
                      record: read.record,
                    });
                    finishInlineConference(
                      read.record,
                      Number(acceptedReference?.submittedRevision)
                    );
                  } catch (caught) {
                    setError(
                      caught instanceof Error
                        ? caught.message
                        : 'Saved conference could not be read. Both drafts remain retained.'
                    );
                  } finally {
                    setReadingInline(false);
                  }
                }}
              >
                Reread saved conference
              </button>
            </div>
          )}
          {usesRelationships && (
            <p role="status" aria-label="Related Record Coverage">
              {relationships.isPending
                ? 'Loading related records…'
                : `${relatedRecords.length} related records loaded.`}
            </p>
          )}
          {usesRelationships && relationships.isError && (
            <p role="status">
              Related records unavailable. Saved associations remain retained.
            </p>
          )}
          {usesRelationships && relationships.hasNextPage && (
            <section aria-label="More Related Records">
              <p>Relationship choices cover loaded records only.</p>
              <button
                className="ws-button"
                type="button"
                disabled={relationships.isFetchingNextPage}
                onClick={() => void relationships.fetchNextPage()}
              >
                {relationships.isFetchingNextPage
                  ? 'Loading related records…'
                  : 'Load more related records'}
              </button>
            </section>
          )}
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
          {wrongStore &&
            health.data?.ready &&
            health.data.mission_journal &&
            sameJournalIdentity(
              targetIdentity(draft.target),
              operatorIdentity(health.data)
            ) &&
            !tray?.pending && (
              <div>
                <p>
                  The original draft stays pinned. Copy its input to the current
                  replay, keeping its mission and leg association.
                </p>
                <button
                  className="ws-button"
                  type="button"
                  onClick={async () => {
                    try {
                      const saved = draft.target.recordId
                        ? (await readOperatorRecord(draft.target.recordId))
                            .record
                        : undefined;
                      if (saved && saved.version !== draft.baseVersion)
                        throw new Error(
                          'The saved record changed. Review its latest version before copying this input.'
                        );
                      const copy = createEditorDraft(
                        workspace.registry,
                        health.data!,
                        draft.input,
                        saved
                      );
                      workspace.registry.parkDraft({
                        ...copy,
                        editorState: {
                          ...draft.editorState,
                          associationMode: 'manual',
                        },
                      });
                      workspace.openDraft(copy.draftId);
                    } catch (error) {
                      setError(
                        error instanceof Error
                          ? error.message
                          : 'Could not copy the retained input.'
                      );
                    }
                  }}
                >
                  Copy input to current replay
                </button>
              </div>
            )}
          {tray &&
            (tray.pending ||
              (draft.target.recordId
                ? tray.target.recordId === draft.target.recordId
                : tray.target.newDraftId === draft.target.newDraftId)) && (
              <div role="status">
                <p>
                  {tray.status.replaceAll('_', ' ')} · {tray.title}
                </p>
                {tray.message && <p>{tray.message}</p>}
                {inlineParentId && tray.pending && tray.retryReady && (
                  <button
                    type="button"
                    className="ws-button"
                    onClick={() => void workspace.retryExact(tray.commandId)}
                  >
                    Retry exact conference save
                  </button>
                )}
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
                {draft.target.recordId &&
                  tray.current?.record_id === draft.target.recordId &&
                  tray.current.version !== draft.baseVersion && (
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
                      Keep my input using current version {tray.current.version}{' '}
                      as base
                    </button>
                  )}
              </div>
            )}
          {contextualAssociation && (
            <div className="rounded border p-3 space-y-2">
              <p className="font-medium">
                Mission association:{' '}
                {automatic
                  ? (inferred?.label ??
                    'Unresolved — choose an override or supply itinerary timing')
                  : draft.input.scope === 'leg'
                    ? (legs.find((leg) => leg.id === draft.input.leg_id)
                        ?.name ?? 'Unresolved leg')
                    : draft.input.record_type === 'conference' &&
                        draft.input.scope === 'mission'
                      ? 'Association unknown'
                      : draft.input.scope.replaceAll('_', ' ')}
              </p>
              {!associationExpanded ? (
                <button
                  type="button"
                  className="ws-button"
                  onClick={() => {
                    if (automatic) update(draft.input);
                    editorState({
                      associationExpanded: true,
                      associationMode: 'manual',
                    });
                  }}
                >
                  Change association
                </button>
              ) : (
                <button
                  type="button"
                  className="ws-button"
                  onClick={() =>
                    editorState({
                      associationExpanded: false,
                      associationMode: 'auto',
                    })
                  }
                >
                  Use suggested association
                </button>
              )}
              {draft.input.record_type === 'conference' && (
                <p className="ws-meta">
                  Configuration is kept for reuse. Establish, verify and close
                  report activity on one leg; a later leg needs a new
                  establishment report.
                </p>
              )}
            </div>
          )}
          <div
            className="ws-draft-context"
            hidden={
              !!draft.target.correctionVersion ||
              (contextualAssociation && !associationExpanded)
            }
          >
            <label>
              {contextualAssociation ? 'Association' : 'Draft Scope'}
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
                <option value="mission">
                  {draft.input.record_type === 'conference'
                    ? 'Unassigned activity'
                    : contextualAssociation
                      ? 'Entire mission'
                      : 'Mission'}
                </option>
                <option value="preflight">Preflight</option>
                <option value="leg">Leg</option>
                <option value="between_legs">Between Legs</option>
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
                  'Previous Leg',
                  draft.input.payload.previous_leg_id,
                  (previous_leg_id) => association({ previous_leg_id })
                )}
                {legSelect(
                  'Next Leg',
                  draft.input.payload.next_leg_id,
                  (next_leg_id) => association({ next_leg_id })
                )}
              </>
            )}
          </div>
          {draft.input.record_type === 'call' ? (
            <CallEditor
              formId={formId}
              key={draft.draftId}
              draft={draft.input as CallInput}
              creating={!draft.target.recordId}
              disabled={false}
              saveDisabled={saveDisabled}
              contextual
              records={relatedRecords}
              onCreateConference={createInlineConference}
              transportChoices={transportCatalog.data?.transports}
              editorState={
                draft.editorState?.call as Partial<CallEditorState> | undefined
              }
              onEditorStateChange={(call) => editorState({ call })}
              onChange={update}
              onSubmit={(value) => void saveInput(value)}
            />
          ) : draft.input.record_type === 'conference' ? (
            <ConferenceEditor
              formId={formId}
              draft={draft.input as ConferenceInput}
              transportOptions={transportCatalog.data?.transports.filter(
                (transport) => transport.enabled && !transport.archived
              )}
              disabled={saveDisabled}
              onChange={update}
              onSubmit={(value) => void saveInput(value)}
            />
          ) : draft.input.record_type === 'participation' ? (
            <>
              {!draft.target.recordId &&
                draft.input.payload.state === 'connected' && (
                  <label className="ws-touch">
                    <input
                      type="checkbox"
                      checked={draft.editorState?.joinNow === true}
                      onChange={(event) => {
                        editorState({ joinNow: event.target.checked });
                        if (event.target.checked)
                          update({
                            ...draft.input,
                            time: {
                              ...draft.input.time,
                              occurred_at: null,
                              precision: 'unknown',
                            },
                          });
                      }}
                    />
                    Report Joined Now Using Backend Zulu
                  </label>
                )}
              {!draft.target.recordId && (
                <p>
                  Leave this unchecked to retain a reported or unknown join
                  time. A conference report does not connect a customer.
                </p>
              )}
              {(!relationships.data || relationships.hasNextPage) && (
                <p role="status">
                  Relationships show loaded records only. Unresolved saved
                  associations remain retained.
                </p>
              )}
              <ParticipationEditor
                formId={formId}
                draft={draft.input}
                records={relatedRecords}
                disabled={saveDisabled}
                onChange={(value) => {
                  update(value);
                  if (value.time.occurred_at) editorState({ joinNow: false });
                }}
                onSubmit={(value) => void saveInput(value)}
              />
            </>
          ) : draft.input.record_type === 'transport_decision' ? (
            <TransportForm
              formId={formId}
              records={relatedRecords}
              draft={{
                input: draft.input,
                replacement_check_row_ids: Array.isArray(
                  draft.editorState?.replacement_check_row_ids
                )
                  ? (draft.editorState.replacement_check_row_ids as string[])
                  : [],
              }}
              record={draft.baseRecord ?? undefined}
              disabled={false}
              saveDisabled={saveDisabled}
              contextual
              onDraftChange={(value) => {
                update(value.input);
                editorState({
                  replacement_check_row_ids: value.replacement_check_row_ids,
                });
              }}
              onSave={async (command) => {
                if (saveDisabled) return false;
                await workspace.submitDraft(draft.draftId, { command });
                return false;
              }}
            />
          ) : draft.input.record_type === 'issue' &&
            draft.target.correctionVersion ? (
            <form
              id={formId}
              aria-label="Correct Historical Update"
              onSubmit={(event) => {
                event.preventDefault();
                if (!saveDisabled) void workspace.submitDraft(draft.draftId);
              }}
            >
              <p>
                Correct Historical Update · current status, mitigation and
                follow-up are preserved.
              </p>
              <label>
                Corrected Update
                <textarea
                  aria-label="Corrected Update"
                  className="ws-field"
                  required
                  maxLength={8000}
                  value={draft.input.payload.update_text ?? ''}
                  onChange={(event) => {
                    if (draft.input.record_type === 'issue')
                      update({
                        ...draft.input,
                        payload: {
                          ...draft.input.payload,
                          update_text: event.target.value,
                        },
                      });
                  }}
                />
              </label>
              <UtcDateTime
                label="Corrected Occurrence"
                value={draft.input.payload.corrected_update_at ?? null}
                parts={
                  draft.editorState?.correctedOccurrenceParts as
                    | UtcParts
                    | undefined
                }
                onPartsChange={(correctedOccurrenceParts) =>
                  editorState({ correctedOccurrenceParts })
                }
                onChange={(corrected_update_at) => {
                  if (draft.input.record_type === 'issue')
                    update({
                      ...draft.input,
                      payload: { ...draft.input.payload, corrected_update_at },
                    });
                }}
              />
              <button hidden className="ws-button" disabled={saveDisabled}>
                Save Correction
              </button>
            </form>
          ) : draft.input.record_type === 'issue' ? (
            <IssueForm
              formId={formId}
              draft={{
                input: draft.input,
                baseVersion: draft.baseVersion,
                occurredAt:
                  typeof draft.editorState?.occurredAt === 'string'
                    ? draft.editorState.occurredAt
                    : null,
                useCurrentTime: draft.editorState?.useCurrentTime !== false,
              }}
              record={draft.baseRecord ?? undefined}
              disabled={false}
              saveDisabled={saveDisabled}
              contextual
              asOf={null}
              related={relatedRecords}
              onDraftChange={(value) => {
                update(value.input);
                editorState({
                  occurredAt: value.occurredAt,
                  useCurrentTime: value.useCurrentTime,
                });
              }}
              onSave={async (command, useCurrentTime) => {
                if (saveDisabled) return false;
                await workspace.submitDraft(draft.draftId, {
                  command,
                  captureCurrentTime: useCurrentTime,
                });
                return false;
              }}
            />
          ) : draft.input.record_type === 'journal_entry' &&
            draft.input.payload.entry_type === 'capability_assessment' ? (
            <CapabilityForm
              formId={formId}
              draft={{
                input:
                  draft.input as import('@/types/operator').CapabilityInput,
                version: draft.baseVersion,
                currentDimensions: Array.isArray(
                  draft.editorState?.currentDimensions
                )
                  ? draft.editorState.currentDimensions.filter(
                      (value): value is 'functional' | 'redundancy' =>
                        value === 'functional' || value === 'redundancy'
                    )
                  : [],
              }}
              record={draft.baseRecord ?? undefined}
              disabled={false}
              saveDisabled={saveDisabled}
              asOf={null}
              onDraftChange={(value) => {
                update(value.input);
                editorState({ currentDimensions: value.currentDimensions });
              }}
              onSave={async (input, version, currentDimensions) => {
                if (saveDisabled) return false;
                const command =
                  draft.target.recordId && version
                    ? {
                        operation: 'update' as const,
                        record_id: draft.target.recordId,
                        body: { ...input, expected_version: version },
                      }
                    : { operation: 'create' as const, body: input };
                await workspace.submitDraft(draft.draftId, {
                  command,
                  captureCurrentTime: true,
                  captureDimensions: currentDimensions,
                });
                return false;
              }}
            />
          ) : draft.input.record_type === 'journal_entry' &&
            ['note', 'call_observation'].includes(
              draft.input.payload.entry_type
            ) ? (
            <JournalEditor
              formId={formId}
              key={`${draft.draftId}:${draft.baseVersion}`}
              missionId={draft.target.missionId}
              record={draft.baseRecord ?? undefined}
              draft={draft.input as JournalInput}
              contextual
              disabled={false}
              saveDisabled={saveDisabled}
              onChange={update}
              captureNow={async () => {
                const clock = await readOperatorRecords({
                  mission_id: draft.target.missionId,
                  record_type: 'journal_entry',
                  limit: 1,
                });
                const source = await getOperatorHealth();
                if (operatorIdentity(source) !== targetIdentity(draft.target))
                  throw new Error(
                    'Source Changed. Keep This Draft And Reopen After Recovery.'
                  );
                return clock.as_of;
              }}
              occurrenceParts={
                draft.editorState?.noteOccurrenceParts as UtcParts | undefined
              }
              onOccurrencePartsChange={(noteOccurrenceParts) =>
                editorState({ noteOccurrenceParts })
              }
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
        </div>
        <div className="ws-editor-footer">
          {saveLabel && (
            <button
              className="ws-button"
              type="submit"
              form={formId}
              disabled={saveDisabled}
            >
              {saveLabel}
            </button>
          )}
          <button
            className="ws-button ws-destructive"
            disabled={
              !!inlineParentId &&
              (!!inlineTray?.pending ||
                !!inlineTray?.receipt ||
                !!acceptedRecordId ||
                inlineTray?.status === 'saving')
            }
            onClick={() => {
              const result = workspace.registry.discardDraft(draft.draftId);
              if (result.state === 'durable') {
                if (inlineParent) {
                  const retainedParent = workspace.registry.resumeDraft(
                    inlineParent.draftId
                  )!;
                  const parentState = { ...retainedParent.editorState };
                  delete parentState.inlineConferenceDraftId;
                  workspace.registry.parkDraft({
                    ...retainedParent,
                    editorState: parentState,
                    revision: retainedParent.revision + 1,
                  });
                }
                returnToParent();
              } else setError(result.message);
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
