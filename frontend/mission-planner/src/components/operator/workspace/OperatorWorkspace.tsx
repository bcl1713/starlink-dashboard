import { LegacySaveRecovery } from './LegacySaveRecovery';
import { operatorTiming } from '@/lib/operatorTiming';
import { readTrainingProviderEvidence } from '../training/trainingProviderEvidence';
import {
  collectRecoveryEvidence,
  retainRecoveryObservation,
} from '../training/trainingRecoveryEvidence';
import {
  collectConflictEvidence,
  retainConflictObservations,
} from '../training/trainingConflictEvidence';
import {
  collectClientEvidence,
  retainClientObservation,
} from '../training/trainingClientEvidence';
import { readTrainingDisplayEvidence } from '../training/trainingDisplayEvidence';
import { collectArchiveEvidence } from '../training/trainingArchiveEvidence';
import {
  retainJournalObservation,
  collectJournalContinuityEvidence,
} from '../training/trainingJournalEvidence';
import {
  captureRetryObservation,
  collectRetryEvidence,
  retainRetryReceipts,
} from '../training/trainingRetryEvidence';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useMission } from '@/hooks/api/useMissions';
import {
  operatorIdentity,
  useOperatorHealth,
} from '@/hooks/api/operatorReadSession';
import { useMissionTimeline } from '@/hooks/api/useMissionTimeline';
import { useOperatorEvents } from '@/hooks/api/useOperatorEvents';
import { readOperatorRecords, readOperatorRecord } from '@/services/operator';
import type {
  JournalInput,
  OperatorCommand,
  OperatorInput,
  SavedRecord,
} from '@/types/operator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { callCommand, type CallAction } from '../callCommands';
import { joinCommand } from '../conferenceCommands';
import { callDraft } from '../callDraft';
import {
  conferenceDraft,
  participationDraft,
  conferenceCommand,
  leaveCommand,
  resumeCommand,
  unknownTime,
} from '../conferenceCommands';
import { OperatorEventFeed } from '../OperatorEventFeed';
import { OperatorAlertSettings } from '../OperatorAlertSettings';
import { OperatorDisplayTools } from '../OperatorDisplayTools';
import { OperatorStoreSetup } from '../OperatorStoreSetup';
import { ManualDestinationSettingsCard } from '../ManualDestinationSettingsCard';
import { useEventAlerts } from '../useEventAlerts';
import { useOperatorWorkspace } from './OperatorWorkspaceProvider';
import { WorkspaceAwareness } from './WorkspaceAwareness';
import { nextRequirement } from './awarenessModel';
import { WorkspaceEditor } from './WorkspaceEditor';
import { MissionContextChooser } from './MissionContextChooser';
import { createEditorDraft } from './editorDraft';
import { CommunicationsView } from './CommunicationsView';
import { JournalHistory } from '../JournalHistory';
import { HistoryView } from './HistoryView';
import { TransportView } from './TransportView';
import { assignmentInput } from './transportAssignments';
import { newTransportDraft } from '../transportForms';
import { capabilityInput } from '../capabilityInput';
import { IssuesView } from './IssuesView';
import { IssueActivity } from '../IssueActivity';
import { issueInput, instant } from '../issueForms';
import { GuidedMission } from '../training/GuidedMission';
import { trainingContext } from '../training/trainingContext';
import {
  collectEventEvidence,
  collectReplayEvidence,
} from '../training/trainingEventEvidence';
import { readEventSnapshot } from '@/services/operatorEvents';
import { simulationRunApi } from '@/services/simulation-run';
import { readTrainingRecords } from '../training/readTrainingRecords';
import {
  retainReplayObservation,
  collectHistoricalReplayEvidence,
} from '../training/trainingReplayEvidence';
import type { TrainingEvidence } from '../training/trainingSteps';
import {
  isCurrentTrainingEvidence,
  type CheckedTrainingEvidence,
} from '../training/trainingEvidence';
import { readOperatingContext } from '@/services/operator';
import {
  activeAssociation,
  defaultAssociation,
  operatingMission,
  operationalRelevant,
  replayCurrent,
} from './operatingContext';
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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const active = useQuery({
    queryKey: ['operator-operating-context'],
    queryFn: readOperatingContext,
    refetchInterval: 2000,
    retry: false,
    networkMode: 'always',
  });
  const missionId = operatingMission(
    params.get('mission_id'),
    active.isError ? undefined : active.data
  );
  const requested = params.get('view');
  const view = views.find((view) => view.toLowerCase() === requested) ?? 'Now';
  const workspace = useOperatorWorkspace();
  const health = useOperatorHealth(false);
  const identity = operatorIdentity(health.data);
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: ['operator-health'] });
  }, [
    queryClient,
    active.data?.source_mode,
    active.data?.replay_run_id,
    active.data?.operating_context_id,
  ]);
  const contextMismatch =
    !active.isError &&
    !!health.data?.mission_journal &&
    !!active.data &&
    (active.data.source_mode !== health.data.source_mode ||
      active.data.replay_run_id !== health.data.replay_run_id ||
      active.data.operating_context_id !== health.data.operating_context_id);
  const currentSource = contextMismatch
    ? {
        ...health.data!,
        replay_run_id: active.data!.replay_run_id,
        operating_context_id: active.data!.operating_context_id,
      }
    : health.data;
  const events = useOperatorEvents(
    missionId,
    !health.isError ? identity : null
  );
  const timeline = useMissionTimeline(
    missionId,
    !health.isError && !contextMismatch ? identity : null
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
  const currentAssociation = activeAssociation(
    active.isError || active.data?.mission_id !== missionId
      ? undefined
      : active.data,
    mission.data
  );
  const snapshotItems = records.data?.pages.flatMap((page) => page.items) ?? [];
  // Only current authoritative GET responses supplement a paginated snapshot.
  // Its H/cursors stay untouched; replay receipts alone never enter this view.
  const confirmed = workspace.confirmedRecords.filter(
    (row) =>
      row.identity === identity && row.read.record.mission_id === missionId
  );
  const merged = new Map(
    snapshotItems.map((item) => [item.record.record_id, item])
  );
  for (const row of confirmed) {
    const previous = merged.get(row.read.record.record_id);
    if (!previous || previous.record.version < row.read.record.version)
      merged.set(row.read.record.record_id, row.read);
  }
  const items = [...merged.values()];
  const renderedConfirmed = useRef(new WeakSet<object>());
  useEffect(() => {
    for (const row of confirmed) {
      if (!renderedConfirmed.current.has(row)) {
        operatorTiming('visible', row.receivedAt);
        renderedConfirmed.current.add(row);
      }
    }
    if (identity)
      workspace.retireConfirmed(
        identity,
        snapshotItems.map((item) => item.record)
      );
    // Snapshot and confirmed-row changes drive catch-up, never a polling timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    records.data,
    identity,
    workspace.confirmedRecords,
    workspace.retireConfirmed,
  ]);
  const loaded = items.map((item) => item.record);
  const currentItems = items.filter((item) =>
    operationalRelevant(item.record, currentSource)
  );
  const currentLoaded = currentItems.map((item) => item.record);
  const retained = items.filter(
    (item) =>
      item.record.record_type !== 'conference' &&
      !replayCurrent(item.record, currentSource)
  );
  const incomplete = !records.data || records.isError || !!records.hasNextPage;
  const disabled =
    !missionId || !health.data?.ready || health.isError || contextMismatch;
  const missionSaveBusy = workspace.tray.some(
    (row) =>
      row.target.missionId === missionId &&
      workspace.busyLanes.includes(row.lane)
  );
  const [tools, setTools] = useState(false);
  const [help, setHelp] = useState(false);
  const [guide, setGuide] = useState(false);
  const [checkedTraining, setCheckedTraining] = useState<
    (CheckedTrainingEvidence & { evidenceRecords: SavedRecord[] }) | null
  >(null);
  const training = trainingContext(
    health.data,
    mission.data,
    window.location.origin
  );
  const trainingIdentity = JSON.stringify(training?.identity);
  const trainingLoading =
    !!missionId && (mission.isPending || health.isPending);
  const trainingEvents = training
    ? collectEventEvidence({
        identity: training.identity,
        namespace: health.data!.simulation_run_id!,
        snapshot: events.snapshot ?? null,
        receivedAt: events.receivedAt,
        browserNow: performance.now(),
        activeLegId: null,
        activeModelIdentity: null,
      })
    : null;
  const trainingRecordsCurrent = isCurrentTrainingEvidence(
    checkedTraining,
    trainingIdentity,
    events.snapshot?.H,
    performance.now(),
    events.snapshot?.generation
  );
  const trainingEvidence: TrainingEvidence = {
    providerStates: trainingRecordsCurrent
      ? checkedTraining.providerStates
      : [],
    available: (trainingEvents?.available ?? false) && !records.isError,
    fresh: !events.failed && (trainingEvents?.fresh ?? false),
    toolingOutcomes: trainingRecordsCurrent
      ? checkedTraining.toolingOutcomes
      : [],
    historicalOutcomes: trainingRecordsCurrent
      ? checkedTraining.historicalOutcomes
      : [],
    outcomes: [
      ...(trainingEvents?.outcomes ?? []),
      ...(trainingRecordsCurrent ? checkedTraining.outcomes : []),
    ],
  };
  const [mobileTools, setMobileTools] = useState(false);
  const [sources, setSources] = useState(false);
  const [operationalAlerts, setOperationalAlerts] = useState(false);
  const [activityId, setActivityId] = useState<string | null>(null);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const noteButton = useRef<HTMLButtonElement>(null);
  function navigateView(view: View) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set('view', view.toLowerCase());
      return next;
    });
  }
  function plannedCall() {
    const input = callDraft(undefined, 'planned', missionId);
    const clock = records.data?.pages[0]?.as_of;
    if (clock)
      input.time.planned_start_at = new Date(
        Math.ceil((Date.parse(clock) + 60_000) / 900_000) * 900_000
      ).toISOString();
    openInput(input);
  }
  function callAction(record: SavedRecord, intent: CallAction) {
    void action(record, (latest, now) => {
      if (intent !== 'connect') return callCommand(latest, intent, now);
      if (
        latest.payload.entry_type !== 'call' ||
        !latest.time.occurred_at ||
        latest.deleted ||
        ['completed', 'cancelled'].includes(latest.payload.status)
      )
        throw new Error(
          'Start an active call before reporting a customer connection.'
        );
      const input = participationDraft(
        latest.mission_id,
        latest.payload.conference_id
      );
      input.scope = latest.scope;
      input.leg_id = latest.leg_id;
      input.payload = {
        ...input.payload,
        call_id: latest.record_id,
        participant: latest.payload.party ?? latest.payload.title,
        title: latest.payload.party ?? latest.payload.title,
        previous_leg_id: latest.payload.previous_leg_id,
        next_leg_id: latest.payload.next_leg_id,
      };
      return joinCommand(input, now);
    });
  }
  function openInput(
    input: OperatorInput,
    record?: SavedRecord,
    joinNow = false
  ) {
    const source = health.data;
    if (!source?.store_id || !source.api_epoch || !source.ready) return;
    input = defaultAssociation(input, currentAssociation, !!record);
    const draft = createEditorDraft(workspace.registry, source, input, record);
    if (!record && currentAssociation)
      workspace.registry.parkDraft({
        ...draft,
        editorState: { associationMode: 'manual' },
      });
    if (joinNow)
      workspace.registry.parkDraft({
        ...draft,
        editorState: { ...draft.editorState, joinNow: true },
      });
    workspace.openDraft(draft.draftId);
  }
  function openRecord(record: SavedRecord) {
    if (record.record_type === 'issue') {
      openInput(issueInput(record.mission_id, record), record);
      return;
    }
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
  async function action(
    record: SavedRecord,
    build: (latest: SavedRecord, now: string) => OperatorCommand
  ) {
    if (acting || disabled || !health.data) return;
    setActing(true);
    setActionError(null);
    try {
      const latest = await readOperatorRecord(record.record_id);
      if (latest.record.version !== record.version) {
        void records.refetch();
        throw new Error(
          'This record changed. Review its current state before choosing the action again.'
        );
      }
      const command = build(latest.record, latest.freshness.as_of);
      const input =
        command.operation === 'create' || command.operation === 'update'
          ? command.body
          : ({
              schema_version: 1,
              record_type: record.record_type,
              mission_id: record.mission_id,
              leg_id: record.leg_id,
              scope: record.scope,
              time: record.time,
              payload: record.payload,
            } as OperatorInput);
      const draft = createEditorDraft(
        workspace.registry,
        health.data,
        input,
        command.operation === 'create' ? undefined : latest.record
      );
      workspace.refreshDrafts();
      await workspace.submitDraft(draft.draftId, { command });
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Action unavailable.'
      );
    } finally {
      setActing(false);
    }
  }
  function transition(record: SavedRecord) {
    void action(record, (latest) => ({
      operation: latest.deleted ? 'restore' : 'remove',
      record_id: latest.record_id,
      body: { schema_version: 1, expected_version: latest.version },
    }));
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
    <main className="operator-workspace" data-view={view.toLowerCase()}>
      <header className="ws-header">
        <div>
          <h1>Operator</h1>
          <p className="ws-mode ws-meta">
            {health.data?.source_mode === 'simulation' ? 'Simulation · ' : ''}
            UTC · Coverage {events.snapshot?.coverage ?? 'unknown'}
            {events.failed ? ' · Feed unavailable' : ''}
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
        <div className="ws-meta" aria-label="Operating context">
          <p>
            {active.isError
              ? 'Active context unavailable'
              : active.data?.mission_name
                ? `Active: ${active.data.mission_name} · ${active.data.leg_name ?? 'Leg unavailable'} · ${active.data.phase?.replaceAll('_', ' ') ?? 'Phase unavailable'}`
                : 'No active mission or leg'}
          </p>
          {params.has('mission_id') && (
            <button
              className="ws-button"
              onClick={() =>
                setParams((previous) => {
                  const next = new URLSearchParams(previous);
                  next.delete('mission_id');
                  return next;
                })
              }
            >
              Return to active mission
            </button>
          )}
          {health.data?.mission_journal && (
            <p className="ws-replay-note">
              Mission journal retained across replays · Evaluation{' '}
              {health.data.simulation_run_id}. Prior replay reports remain in
              History; they do not establish current connections or readiness.
            </p>
          )}
        </div>
        <div
          className="ws-header-actions"
          onKeyDown={(event) => {
            if (event.key === 'Escape') setMobileTools(false);
          }}
        >
          <button
            className="ws-button ws-mobile-tools-toggle"
            aria-expanded={mobileTools}
            aria-controls="operator-tool-controls"
            onClick={() => setMobileTools((value) => !value)}
          >
            Tools
          </button>
          <div
            className="ws-tool-controls"
            id="operator-tool-controls"
            data-open={mobileTools}
          >
            {missionId && (
              <Link
                className="ws-button"
                to={`/missions/${encodeURIComponent(missionId)}`}
              >
                Mission records
              </Link>
            )}
            <button
              className="ws-button"
              onClick={() => {
                setMobileTools(false);
                setTools(true);
              }}
            >
              Display tools
            </button>
            <OperatorAlertSettings
              preferences={alerts.preferences}
              onChange={alerts.updatePreferences}
              delivery={alerts.delivery}
              onEnable={alerts.enableOutput}
            />
            <button
              className="ws-button ws-mobile-only"
              onClick={() => {
                setMobileTools(false);
                setSources(true);
              }}
            >
              Source status
            </button>
          </div>
          <button className="ws-button" onClick={() => setHelp(true)}>
            Help
          </button>
        </div>
      </header>
      <div className="ws-content">
        <WorkspaceAwareness
          snapshot={events.snapshot}
          timeline={timeline}
          onOpenTimelineSource={(event) => {
            if (
              event.kind === 'issue_followup' ||
              event.kind.startsWith('call_')
            ) {
              const record = loaded.find(
                (record) => record.record_id === event.source_ref
              );
              if (record) {
                openRecord(record);
                return;
              }
              if (event.source_ref) {
                setHistoryId(event.source_ref);
                return;
              }
            } else if (event.leg_id) {
              navigate(
                `/missions/${encodeURIComponent(event.mission_id)}/legs/${encodeURIComponent(event.leg_id)}`
              );
              return;
            }
            navigateView(
              event.kind === 'issue_followup'
                ? 'Issues'
                : event.kind.startsWith('call_')
                  ? 'Communications'
                  : 'Transport'
            );
          }}
          next={nextRequirement(events.snapshot)}
          records={currentLoaded}
          recordsIncomplete={incomplete}
          failed={events.failed || health.isError}
          onOpenRecord={openRecord}
          onOpenEvents={() => setOperationalAlerts(true)}
          onOpenNext={() => {
            const next = nextRequirement(events.snapshot);
            const record = loaded.find(
              (record) =>
                record.record_type === 'call' &&
                next?.dependent_versions[record.record_id] !== undefined
            );
            if (record) openRecord(record);
            else navigateView('Communications');
          }}
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
          {guide && training && (
            <GuidedMission
              identity={training.identity}
              evidence={trainingEvidence}
              onDismiss={() => setGuide(false)}
              onCheckEvidence={async (previous, stage) => {
                setCheckedTraining(null);
                let clientObservations = retainClientObservation(
                  training.identity,
                  health.data!.simulation_run_id!,
                  events.snapshot?.H ?? -1,
                  navigator.onLine,
                  workspace.registry.listDrafts(),
                  previous.clientObservations ?? [],
                  Date.now(),
                  checkedTraining?.identity === trainingIdentity
                    ? checkedTraining.evidenceRecords
                    : []
                );
                if (!navigator.onLine)
                  return {
                    ...previous,
                    clientObservations,
                    unavailableReason:
                      'Offline: retain the draft and reconnect before checking backend evidence.',
                  };
                const checked = await readTrainingRecords(
                  training.identity,
                  health.data!.simulation_run_id!,
                  training.prerequisiteIds
                );
                const [
                  replay,
                  snapshot,
                  currentMission,
                  displayOutcomes,
                  providers,
                ] = await Promise.all([
                  simulationRunApi.get(),
                  readEventSnapshot(missionId),
                  mission.refetch(),
                  readTrainingDisplayEvidence(),
                  stage === 'T11'
                    ? readTrainingProviderEvidence()
                    : Promise.resolve({ providerStates: [], outcomes: [] }),
                ]);
                const currentContext = trainingContext(
                  health.data,
                  currentMission.data,
                  window.location.origin
                );
                if (
                  currentMission.isError ||
                  !currentMission.data ||
                  !currentContext ||
                  JSON.stringify(currentContext.identity) !==
                    trainingIdentity ||
                  JSON.stringify(currentContext.prerequisiteIds) !==
                    JSON.stringify(training.prerequisiteIds)
                )
                  throw new Error(
                    'Private mission changed or is unavailable; reopen it before checking evidence.'
                  );
                const observed = collectEventEvidence({
                  identity: training.identity,
                  namespace: health.data!.simulation_run_id!,
                  snapshot,
                  receivedAt: performance.now(),
                  browserNow: performance.now(),
                  activeLegId: null,
                  activeModelIdentity: null,
                });
                if (
                  !checked.available ||
                  !checked.fresh ||
                  !observed.available ||
                  checked.H !== snapshot.H
                )
                  throw new Error(
                    'Training evidence changed while checking; check again.'
                  );
                const namespace = health.data!.simulation_run_id!;
                clientObservations = retainClientObservation(
                  training.identity,
                  namespace,
                  checked.H!,
                  true,
                  workspace.registry.listDrafts(),
                  previous.clientObservations ?? [],
                  Date.now(),
                  checked.evidenceRecords
                );
                const observations = [...(previous.retryObservations ?? [])];
                for (const transaction of workspace.tray) {
                  if (
                    observations.some(
                      (item) => item.request.key === transaction.commandId
                    )
                  )
                    continue;
                  const captured = captureRetryObservation(
                    training.identity,
                    namespace,
                    transaction,
                    workspace.attempts,
                    checked.evidenceRecords
                  );
                  if (captured) observations.push(captured);
                }
                const retainedObservations = retainRetryReceipts(
                  training.identity,
                  namespace,
                  observations.slice(-20),
                  workspace.attempts,
                  workspace.tray,
                  checked.evidenceRecords
                );
                const retryOutcomes = collectRetryEvidence(
                  training.identity,
                  namespace,
                  retainedObservations,
                  workspace.attempts,
                  workspace.tray,
                  checked.evidenceRecords
                );
                const replayObservations = retainReplayObservation(
                  training.identity,
                  namespace,
                  currentMission.data.legs,
                  snapshot,
                  replay,
                  previous.replayObservations ?? []
                );
                const currentReplayOutcomes = collectReplayEvidence(
                  snapshot,
                  replay,
                  currentMission.data.legs
                );
                const historicalReplayOutcomes =
                  collectHistoricalReplayEvidence(
                    training.identity,
                    namespace,
                    currentMission.data.legs,
                    snapshot.as_of,
                    snapshot.H,
                    replayObservations
                  );
                const journalObservations = retainJournalObservation(
                  training.identity,
                  namespace,
                  snapshot,
                  replay,
                  checked.evidenceRecords,
                  previous.journalObservations ?? []
                );
                const journalOutcomes = collectJournalContinuityEvidence(
                  training.identity,
                  namespace,
                  currentMission.data.legs,
                  snapshot.as_of,
                  snapshot.H,
                  checked.evidenceRecords,
                  training.prerequisiteIds,
                  journalObservations
                );
                const conflictObservations = retainConflictObservations(
                  training.identity,
                  namespace,
                  previous.conflictObservations ?? [],
                  workspace.tray,
                  workspace.attempts,
                  checked.evidenceRecords
                );
                const conflictOutcomes = collectConflictEvidence(
                  training.identity,
                  namespace,
                  checked.H,
                  checked.evidenceRecords,
                  conflictObservations
                );
                const recoveryObservation = retainRecoveryObservation(
                  training.identity,
                  namespace,
                  previous.recoveryObservation,
                  workspace.tray
                );
                const recoveryOutcomes = collectRecoveryEvidence(
                  training.identity,
                  namespace,
                  checked.H,
                  checked.evidenceRecords,
                  recoveryObservation
                );
                const clientOutcomes = collectClientEvidence(
                  training.identity,
                  namespace,
                  checked.H,
                  checked.evidenceRecords,
                  clientObservations
                );
                const archiveOutcomes = collectArchiveEvidence(
                  training.identity,
                  namespace,
                  checked.H,
                  checked.evidenceRecords,
                  previous.archiveObservations
                );
                setCheckedTraining({
                  ...checked,
                  providerStates: providers.providerStates,
                  toolingOutcomes: [...archiveOutcomes, ...recoveryOutcomes],
                  historicalOutcomes: [
                    ...conflictOutcomes,
                    ...clientOutcomes,
                    ...journalOutcomes,
                    ...historicalReplayOutcomes.filter(
                      (outcome) => !currentReplayOutcomes.includes(outcome)
                    ),
                  ],
                  outcomes: [
                    ...new Set([
                      ...checked.outcomes,
                      ...displayOutcomes,
                      ...providers.outcomes,
                      ...conflictOutcomes,
                      ...clientOutcomes,
                      ...retryOutcomes,
                      ...journalOutcomes,
                      ...archiveOutcomes,
                      ...recoveryOutcomes,
                      ...observed.outcomes,
                      ...currentReplayOutcomes,
                      ...historicalReplayOutcomes,
                    ]),
                  ],
                  identity: trainingIdentity,
                  eventGeneration: snapshot.generation,
                  checkedAt: performance.now(),
                });
                events.refresh();
                return {
                  recoveryObservation,
                  conflictObservations,
                  clientObservations,
                  retryObservations: retainedObservations,
                  replayObservations,
                  journalObservations,
                  archiveObservations: previous.archiveObservations ?? [],
                };
              }}
              onOpenTarget={(stage) => {
                if (stage === 'T10') navigate('/missions');
                else if (['T05', 'T09'].includes(stage))
                  navigate(`/missions/${encodeURIComponent(missionId)}`);
                else
                  navigateView(
                    stage === 'T02' || stage === 'T03'
                      ? 'Communications'
                      : stage === 'T06'
                        ? 'Transport'
                        : stage === 'T07'
                          ? 'Issues'
                          : stage === 'T08'
                            ? 'Notes'
                            : stage === 'T11'
                              ? 'History'
                              : 'Now'
                  );
              }}
            />
          )}
          <div hidden={view !== 'Now'}>
            <ManualDestinationSettingsCard />
          </div>
          <OperatorStoreSetup
            health={health.data}
            error={health.error}
            refresh={() => health.refetch()}
          />
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
              <div className="ws-quick-actions" hidden={view === 'Transport'}>
                <button
                  className="ws-button ws-primary"
                  disabled={disabled}
                  onClick={plannedCall}
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
              {records.isFetching && records.data && (
                <p role="status">Refreshing saved records…</p>
              )}
              {actionError && <p role="alert">{actionError}</p>}
              {view === 'Communications' || view === 'Now' ? (
                <>
                  <CommunicationsView
                    activeOnly={view === 'Now'}
                    items={currentItems}
                    currentAssociation={currentAssociation}
                    isSessionCurrent={(record) =>
                      replayCurrent(record, currentSource)
                    }
                    mission={mission.data}
                    disabled={
                      disabled ||
                      acting ||
                      missionSaveBusy ||
                      (!records.data && !confirmed.length)
                    }
                    incomplete={incomplete}
                    asOf={records.data?.pages[0]?.as_of}
                    onCreateCall={plannedCall}
                    onCallAction={callAction}
                    onCreateActualCall={() =>
                      openInput(
                        callDraft(undefined, 'retrospective', missionId)
                      )
                    }
                    onCreateConference={() =>
                      openInput(conferenceDraft(missionId))
                    }
                    onJoin={(conference) =>
                      openInput(
                        participationDraft(missionId, conference?.record_id),
                        undefined,
                        true
                      )
                    }
                    onEdit={openRecord}
                    onHistory={setHistoryId}
                    onTransition={transition}
                    onConferenceAction={(record, intent) =>
                      void action(record, (latest, now) =>
                        conferenceCommand(
                          latest,
                          intent,
                          now,
                          currentAssociation,
                          replayCurrent(latest, currentSource)
                        )
                      )
                    }
                    onCustomerAction={(record, intent) =>
                      void action(record, (latest, now) =>
                        intent === 'restore'
                          ? resumeCommand(latest, now)
                          : leaveCommand(latest, intent, now)
                      )
                    }
                  />
                </>
              ) : view === 'Transport' ? (
                <TransportView
                  key={`${missionId}:${identity}`}
                  missionId={missionId}
                  identity={identity}
                  records={loaded}
                  legId={currentAssociation?.leg_id ?? null}
                  onApply={async (service, transport) => {
                    if (!health.data || disabled)
                      throw new Error('Operator store unavailable.');
                    const clock = records.data?.pages[0]?.as_of;
                    if (!clock)
                      throw new Error(
                        'Refresh mission records before applying.'
                      );
                    const input = assignmentInput(
                      missionId,
                      service,
                      transport,
                      clock,
                      currentAssociation
                    );
                    const draft = createEditorDraft(
                      workspace.registry,
                      health.data,
                      input
                    );
                    workspace.refreshDrafts();
                    let accepted = false;
                    await workspace.submitDraft(draft.draftId, {
                      onAccepted: () => {
                        accepted = true;
                      },
                      atCurrentTime: (now) => ({
                        operation: 'create',
                        body: assignmentInput(
                          missionId,
                          service,
                          transport,
                          now,
                          currentAssociation
                        ),
                      }),
                    });
                    if (!accepted)
                      throw new Error(
                        'Assignment not confirmed. Review the save status below before retrying.'
                      );
                  }}
                  events={events}
                  disabled={
                    disabled ||
                    acting ||
                    records.isFetching ||
                    missionSaveBusy ||
                    workspace.tray.some(
                      (row) =>
                        row.target.missionId === missionId &&
                        row.target.recordType === 'transport_decision' &&
                        (!!row.pending || row.status === 'accepted_unreadable')
                    )
                  }
                  onCreate={() => openInput(newTransportDraft(missionId).input)}
                  onEdit={openRecord}
                  onHistory={setHistoryId}
                  onTransition={transition}
                />
              ) : view === 'Issues' ? (
                <IssuesView
                  pages={(records.data?.pages ?? []).map((page) => ({
                    ...page,
                    items: page.items.filter((item) =>
                      operationalRelevant(item.record, currentSource)
                    ),
                  }))}
                  incomplete={incomplete}
                  unavailable={records.isError}
                  disabled={
                    disabled || acting || records.isFetching || missionSaveBusy
                  }
                  onCreate={() => openInput(issueInput(missionId))}
                  onCreateCapability={() =>
                    openInput(capabilityInput(missionId))
                  }
                  onEdit={openRecord}
                  onHistory={setHistoryId}
                  onActivity={setActivityId}
                  onTransition={transition}
                  onAction={(record, status) =>
                    void action(record, (latest, now) => {
                      const input = issueInput(missionId, latest);
                      return {
                        operation: 'update',
                        record_id: latest.record_id,
                        body: {
                          ...input,
                          expected_version: latest.version,
                          time: instant(now),
                          payload: {
                            ...input.payload,
                            status,
                            ...(status === 'resolved'
                              ? { follow_up_at: null }
                              : {}),
                          },
                        },
                      };
                    })
                  }
                />
              ) : (
                <HistoryView
                  items={items}
                  incomplete={incomplete}
                  disabled={
                    disabled || acting || records.isFetching || missionSaveBusy
                  }
                  onEdit={openRecord}
                  onHistory={setHistoryId}
                  onTransition={transition}
                  mission={mission.data}
                  notesOnly={view === 'Notes'}
                />
              )}
              {!!retained.length &&
                ['Communications', 'Transport', 'Issues'].includes(view) && (
                  <section aria-label="Previous operational records">
                    <h3>
                      Previous operational records · {retained.length} loaded
                    </h3>
                    <p>Historical reports, not current operational evidence.</p>
                    <button
                      className="ws-button"
                      onClick={() => navigateView('History')}
                    >
                      Browse retained records and history
                    </button>
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
          <LegacySaveRecovery />
          <section aria-label="Save status">
            <h2>Save status</h2>
            {workspace.tray.map((row) => (
              <div className="ws-record" key={row.lane}>
                <p>
                  {row.title} · {row.status.replaceAll('_', ' ')}
                </p>
                <p>{row.message}</p>
                {row.pending &&
                  row.status === 'uncertain' &&
                  !row.retryReady && (
                    <p role="status">
                      Waiting for the retained request and current store…
                    </p>
                  )}
                {row.pending && (
                  <button
                    className="ws-button"
                    disabled={
                      !row.retryReady ||
                      row.status === 'saving' ||
                      row.status === 'quarantined'
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
        </div>
        <WorkspaceEditor
          mission={editorMission.data}
          onReturnFocus={() => noteButton.current?.focus()}
        />
      </div>
      <Dialog
        open={!!activityId}
        onOpenChange={(open) => {
          if (!open) setActivityId(null);
        }}
      >
        <DialogContent className="ws-editor">
          <DialogTitle>Issue activity</DialogTitle>
          <DialogDescription>
            Operational updates and their corrections, with immutable audit
            history.
          </DialogDescription>
          <div className="ws-editor-body">
            {activityId && identity && (
              <IssueActivity
                id={activityId}
                identity={identity}
                disabled={disabled}
                onCorrect={(target) => {
                  const current = loaded.find(
                    (record) => record.record_id === activityId
                  );
                  if (
                    !current ||
                    current.deleted ||
                    target.payload.entry_type !== 'issue'
                  )
                    return;
                  const input = issueInput(current.mission_id, current);
                  input.payload.corrects_version = target.version;
                  input.payload.update_text = target.payload.update_text ?? '';
                  input.payload.corrected_update_at = target.payload
                    .corrects_version
                    ? target.payload.corrected_update_at
                    : target.time.occurred_at;
                  setActivityId(null);
                  openInput(input, current);
                }}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!historyId}
        onOpenChange={(open) => {
          if (!open) setHistoryId(null);
        }}
      >
        <DialogContent className="ws-editor">
          <DialogTitle>Record history</DialogTitle>
          <DialogDescription>
            Saved immutable revisions for the selected record.
          </DialogDescription>
          <div className="ws-editor-body">
            {historyId && identity && (
              <JournalHistory
                id={historyId}
                identity={identity}
                onClose={() => setHistoryId(null)}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
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
          <div className="flex flex-wrap gap-3">
            <Link
              className="ws-button inline-flex items-center"
              to={`/operator/help?returnTo=${encodeURIComponent(`/operator?${params.toString()}`)}`}
            >
              User guide
            </Link>
            <Link
              className="ws-button inline-flex items-center"
              to={`/operator/help?doc=quick-reference&returnTo=${encodeURIComponent(`/operator?${params.toString()}`)}`}
            >
              Quick reference
            </Link>
          </div>
          <button
            className="ws-button"
            disabled={trainingLoading || mission.isError}
            onClick={() => {
              if (training) {
                setHelp(false);
                setGuide(true);
              } else setGuide(true);
            }}
          >
            Guided mission walkthrough
          </button>
          {trainingLoading && (
            <p role="status">
              Checking the selected mission and private training identity…
            </p>
          )}
          {mission.isError && (
            <div className="space-y-2">
              <p role="alert">
                Mission details could not be loaded. Retry the read before
                opening private training; retained drafts and saves keep their
                original targets.
              </p>
              <button
                className="ws-button"
                onClick={() => void mission.refetch()}
              >
                Retry mission details
              </button>
            </div>
          )}
          {guide && !training && (
            <p role="status">
              Training requires a separate private instance on a nonproduction
              computer. From the repository, run scripts/operator-training.sh
              start --root /path/to/a/new-empty-training-root, then open its
              printed address and select Fictional Meridian 21. The guide does
              not switch this operational instance into training mode.
            </p>
          )}
          <p>
            Missions owns itinerary planning and mission records. Configuration
            owns global settings. All times are UTC; unknown times remain
            unknown.
          </p>
        </DialogContent>
      </Dialog>
      <Dialog open={operationalAlerts} onOpenChange={setOperationalAlerts}>
        <DialogContent className="ws-editor">
          <DialogTitle>Operational alerts</DialogTitle>
          <DialogDescription>
            Current operational alert window. Optional acknowledgment changes
            alerts only.
          </DialogDescription>
          <OperatorEventFeed
            events={events}
            onClose={() => setOperationalAlerts(false)}
            onOpenSource={(event) =>
              navigateView(
                event.kind === 'issue_followup'
                  ? 'Issues'
                  : event.kind.startsWith('call_')
                    ? 'Communications'
                    : 'Transport'
              )
            }
          />
        </DialogContent>
      </Dialog>
      <Dialog open={sources} onOpenChange={setSources}>
        <DialogContent>
          <DialogTitle>Source status</DialogTitle>
          <DialogDescription>
            Current event coverage and source freshness.
          </DialogDescription>
          <p>
            Coverage {events.snapshot?.coverage ?? 'unknown'}
            {events.failed ? ' · feed unavailable, last known snapshot' : ''}
          </p>
          {events.snapshot?.sources.map((source) => (
            <p key={source.source}>
              {source.source} · {source.freshness} ·{' '}
              {source.aligned ? 'aligned' : 'not aligned'}
              {source.reason ? ` · ${source.reason}` : ''}
            </p>
          ))}
        </DialogContent>
      </Dialog>
    </main>
  );
}
