import { useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useMission } from '@/hooks/api/useMissions';
import {
  operatorIdentity,
  useOperatorHealth,
} from '@/hooks/api/operatorReadSession';
import { useOperatorEvents } from '@/hooks/api/useOperatorEvents';
import { readOperatorRecords } from '@/services/operator';
import type {
  JournalInput,
  OperatorInput,
  SavedRecord,
} from '@/types/operator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { callDraft } from '../callDraft';
import { conferenceDraft, unknownTime } from '../conferenceCommands';
import { OperatorEventFeed } from '../OperatorEventFeed';
import { OperatorAlertSettings } from '../OperatorAlertSettings';
import { OperatorDisplayTools } from '../OperatorDisplayTools';
import { useEventAlerts } from '../useEventAlerts';
import { useOperatorWorkspace } from './OperatorWorkspaceProvider';
import { WorkspaceAwareness } from './WorkspaceAwareness';
import { nextRequirement } from './awarenessModel';
import { WorkspaceEditor } from './WorkspaceEditor';
import { MissionContextChooser } from './MissionContextChooser';
import './workspace.css';

const views = [
  'Now',
  'Communications',
  'Transport',
  'Issues',
  'Notes',
  'History',
] as const;
type View = (typeof views)[number];

export function OperatorWorkspace() {
  const [params, setParams] = useSearchParams();
  const missionId = params.get('mission_id') ?? '';
  const requested = params.get('view');
  const view = views.find((view) => view.toLowerCase() === requested) ?? 'Now';
  const workspace = useOperatorWorkspace();
  const health = useOperatorHealth(false);
  const identity = operatorIdentity(health.data);
  const events = useOperatorEvents(
    missionId,
    !health.isError ? identity : null
  );
  const alerts = useEventAlerts(events);
  const mission = useMission(missionId);
  const selectedDraft = workspace.selectedDraftId
    ? workspace.registry.resumeDraft(workspace.selectedDraftId)
    : null;
  const editorMission = useMission(selectedDraft?.target.missionId ?? '');
  const records = useInfiniteQuery({
    queryKey: ['operator-records', missionId, identity, 'workspace-all'],
    queryFn: ({ pageParam }) =>
      readOperatorRecords(
        { mission_id: missionId, include_removed: true },
        pageParam
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    enabled: !!missionId && !!identity && !health.isError,
    retry: false,
    networkMode: 'always',
  });
  const items = records.data?.pages.flatMap((page) => page.items) ?? [];
  const loaded = items.map((item) => item.record);
  const incomplete = !records.data || records.isError || !!records.hasNextPage;
  const disabled = !missionId || !health.data?.ready || health.isError;
  const [tools, setTools] = useState(false);
  const [help, setHelp] = useState(false);
  const noteButton = useRef<HTMLButtonElement>(null);
  function navigateView(view: View) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set('view', view.toLowerCase());
      return next;
    });
  }
  function openInput(input: OperatorInput, record?: SavedRecord) {
    const source = health.data;
    if (!source?.store_id || !source.api_epoch || !source.ready) return;
    let draft = workspace.registry.createDraft(
      {
        storeId: source.store_id,
        epoch: source.api_epoch,
        sourceMode: source.source_mode,
        simulationRunId: source.simulation_run_id,
        missionId: input.mission_id,
        recordType: input.record_type,
        recordId: record?.record_id ?? null,
        newDraftId: null,
        scope: input.scope,
        legId: input.leg_id,
        previousLegId: input.payload.previous_leg_id,
        nextLegId: input.payload.next_leg_id,
        correctionVersion: null,
      },
      input
    );
    if (record)
      draft = workspace.registry.parkDraft({
        ...draft,
        baseRecord: record,
        baseVersion: record.version,
      });
    workspace.openDraft(draft.draftId);
  }
  function openRecord(record: SavedRecord) {
    if (
      record.record_type === 'risk' ||
      record.record_type === 'transport_report'
    )
      return;
    openInput(
      {
        schema_version: 1,
        record_type: record.record_type,
        mission_id: record.mission_id,
        leg_id: record.leg_id,
        scope: record.scope,
        time: { ...record.time },
        payload: { ...record.payload },
      } as OperatorInput,
      record
    );
  }
  function note() {
    const input: JournalInput = {
      schema_version: 1,
      record_type: 'journal_entry',
      mission_id: missionId,
      leg_id: null,
      scope: 'mission',
      time: { ...unknownTime },
      payload: {
        schema_version: 1,
        entry_type: 'note',
        title: '',
        note: '',
        previous_leg_id: null,
        next_leg_id: null,
      },
    };
    openInput(input);
  }
  const cue = alerts.batch?.events.filter((event) =>
    events.snapshot?.events.some(
      (current) =>
        current.notification.generation === event.notification.generation &&
        !current.notification.acknowledged &&
        !current.notification.retired
    )
  );
  return (
    <main className="operator-workspace">
      <header className="ws-header">
        <div>
          <h1>Operator</h1>
          <p className="ws-mode ws-meta">
            {health.data?.source_mode === 'simulation' ? 'Simulation · ' : ''}
            UTC · Coverage {events.snapshot?.coverage ?? 'unknown'}
          </p>
        </div>
        <MissionContextChooser
          missionId={missionId}
          onChange={(id) =>
            setParams((previous) => {
              const next = new URLSearchParams(previous);
              if (id) next.set('mission_id', id);
              else next.delete('mission_id');
              return next;
            })
          }
        />
        <div className="ws-header-actions">
          {missionId && (
            <Link
              className="ws-button"
              to={`/missions/${encodeURIComponent(missionId)}`}
            >
              Mission records
            </Link>
          )}
          <button className="ws-button" onClick={() => setTools(true)}>
            Display tools
          </button>
          <OperatorAlertSettings
            preferences={alerts.preferences}
            onChange={alerts.updatePreferences}
            delivery={alerts.delivery}
            onEnable={alerts.enableOutput}
          />
          <button className="ws-button" onClick={() => setHelp(true)}>
            Help
          </button>
        </div>
      </header>
      <WorkspaceAwareness
        snapshot={events.snapshot}
        next={nextRequirement(events.snapshot)}
        records={loaded}
        recordsIncomplete={incomplete}
        failed={events.failed || health.isError}
        onOpenRecord={openRecord}
        onOpenEvents={() => navigateView('Now')}
      />
      <nav className="ws-navigation" aria-label="Operator workspace">
        {views.map((name) => (
          <button
            className="ws-button"
            key={name}
            aria-current={view === name ? 'page' : undefined}
            onClick={() => navigateView(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      <div className="ws-body">
        {!missionId ? (
          <section>
            <h2>Choose a mission</h2>
            <p>
              Select a mission above. Missions owns the itinerary and leg
              activation.
            </p>
            <Link className="ws-button" to="/missions">
              Browse missions
            </Link>
          </section>
        ) : (
          <>
            <div className="ws-quick-actions">
              <button
                className="ws-button ws-primary"
                disabled={disabled}
                onClick={() =>
                  openInput(callDraft(undefined, 'planned', missionId))
                }
              >
                Create call
              </button>
              <button
                className="ws-button"
                disabled={disabled}
                onClick={() => openInput(conferenceDraft(missionId))}
              >
                Create conference
              </button>
              <button
                className="ws-button"
                ref={noteButton}
                disabled={disabled}
                onClick={note}
              >
                Note
              </button>
            </div>
            {disabled && (
              <p role="status">
                {health.data?.enabled === false
                  ? 'Operator store is disabled.'
                  : 'Operator store unavailable. Retained drafts remain available below.'}
              </p>
            )}
            {cue?.length ? (
              <p role="status">
                Local cue: {cue.map((event) => event.title).join(' · ')}
              </p>
            ) : null}
            {view === 'Now' ? (
              <section aria-label="Mission activity">
                <h2>Mission activity</h2>
                <OperatorEventFeed events={events} onClose={() => undefined} />
              </section>
            ) : (
              <section aria-label={view}>
                <h2>{view}</h2>
                {loaded
                  .filter(
                    (record) =>
                      view === 'History' ||
                      (!record.deleted &&
                        (view === 'Communications'
                          ? ['call', 'conference', 'participation'].includes(
                              record.record_type
                            )
                          : view === 'Transport'
                            ? record.record_type.startsWith('transport_')
                            : view === 'Issues'
                              ? record.record_type === 'issue' ||
                                record.payload.entry_type ===
                                  'capability_assessment'
                              : record.record_type === 'journal_entry'))
                  )
                  .map((record) => (
                    <article className="ws-record" key={record.record_id}>
                      <h3>{record.payload.title || 'Untitled record'}</h3>
                      <p className="ws-meta">
                        {record.payload.entry_type.replaceAll('_', ' ')} ·
                        version {record.version}
                        {record.deleted ? ' · removed' : ''}
                      </p>
                      <p>{record.payload.note}</p>
                      {!record.deleted && (
                        <button
                          className="ws-button"
                          disabled={disabled}
                          onClick={() => openRecord(record)}
                        >
                          Open record
                        </button>
                      )}
                    </article>
                  ))}
              </section>
            )}
            {incomplete && (
              <p role="status">
                Loaded records only. Summary and filters do not cover unread
                pages.
              </p>
            )}
            {records.hasNextPage && (
              <button
                className="ws-button"
                disabled={records.isFetchingNextPage}
                onClick={() => void records.fetchNextPage()}
              >
                Load more records
              </button>
            )}
            {records.isError && (
              <button
                className="ws-button"
                onClick={() => void records.refetch()}
              >
                Retry records
              </button>
            )}
          </>
        )}
        <section aria-label="Retained drafts">
          <h2>Drafts</h2>
          {workspace.registry.listDrafts().map((draft) => (
            <button
              className="ws-button"
              key={draft.draftId}
              onClick={() => workspace.openDraft(draft.draftId)}
            >
              {draft.input.payload.title ||
                `New ${draft.input.payload.entry_type}`}{' '}
              ·{' '}
              {draft.target.missionId === missionId
                ? (mission.data?.name ?? missionId)
                : draft.target.missionId}
            </button>
          ))}
        </section>
        <section aria-label="Save status">
          <h2>Save status</h2>
          {workspace.tray.map((row) => (
            <div className="ws-record" key={row.lane}>
              <p>
                {row.title} · {row.status.replaceAll('_', ' ')}
              </p>
              <p>{row.message}</p>
              {row.pending && (
                <button
                  className="ws-button"
                  disabled={
                    row.status === 'saving' || row.status === 'quarantined'
                  }
                  onClick={() => void workspace.retryExact(row.commandId)}
                >
                  Retry same save
                </button>
              )}
              {[
                'quarantined',
                'needs_review',
                'accepted_unreadable',
                'storage_error',
              ].includes(row.status) && (
                <button
                  className="ws-button"
                  onClick={() =>
                    void workspace.rereadAndReconcile(row.commandId)
                  }
                >
                  Reread and reconcile
                </button>
              )}
            </div>
          ))}
        </section>
        {workspace.recoveryErrors.map((message, i) => (
          <p role="alert" key={i}>
            {message}
          </p>
        ))}
        <Link
          className="ws-button"
          to={`/operator?mission_id=${encodeURIComponent(missionId)}`}
        >
          Previous workspace
        </Link>
      </div>
      <WorkspaceEditor
        mission={editorMission.data}
        onReturnFocus={() => noteButton.current?.focus()}
      />
      <Dialog open={tools} onOpenChange={setTools}>
        <DialogContent className="ws-editor">
          <DialogTitle>Display tools</DialogTitle>
          <DialogDescription>
            Shared Overview settings and commands to a selected window in this
            browser.
          </DialogDescription>
          <div className="ws-editor-body">
            <OperatorDisplayTools missionId={missionId} />
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent>
          <DialogTitle>Operator Help</DialogTitle>
          <DialogDescription>
            Reports record actions and observations; they do not control
            communications hardware.
          </DialogDescription>
          <p>
            Create calls for requirements. Create a reusable conference, report
            its state, then report each customer joining or leaving
            independently. Keep a draft before changing mission; its target
            stays pinned.
          </p>
          <p>
            Missions owns itinerary planning and mission records. Configuration
            owns global settings. All times are UTC; unknown times remain
            unknown.
          </p>
        </DialogContent>
      </Dialog>
    </main>
  );
}
