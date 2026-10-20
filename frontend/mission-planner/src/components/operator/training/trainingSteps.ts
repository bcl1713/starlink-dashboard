import type { TrainingProgress } from './trainingProgress';
import type { TrainingProviderState } from './trainingProviderEvidence';

export const trainingSteps = [
  {
    id: 'T01',
    title: 'Identify your private mission and scope',
    route: '/operator',
    target: 'mission-context',
    guide: 'context',
    outcomes: ['private-context-read'],
    manual: ['context-understood'],
  },
  {
    id: 'T02',
    title: 'Plan, log, reschedule and recover calls',
    route: '/operator',
    target: 'communications',
    guide: 'calls',
    outcomes: [
      'call-created',
      'call-rescheduled',
      'call-completed',
      'call-cancelled-reinstated',
      'call-removed-restored',
      'call-unknown-time',
      'call-prep-zero',
      'call-history',
    ],
    manual: [],
  },
  {
    id: 'T03',
    title: 'Operate a conference and independent customer intervals',
    route: '/operator',
    target: 'communications',
    guide: 'conferences',
    outcomes: [
      'conference-established-verified',
      'conference-interrupted-restored',
      'conference-reused-closed',
      'participation-joined-left',
      'participation-resumed-new-interval',
      'participation-overlap',
      'participation-discrepancy',
    ],
    manual: ['bridge-report-semantics'],
  },
  {
    id: 'T04',
    title: 'Use display controls and foreground alerts',
    route: '/operator',
    target: 'tools',
    guide: 'display-alerts',
    outcomes: ['event-acknowledged', 'display-settings-read'],
    manual: [
      'overview-recenter',
      'display-presets-groups-history',
      'foreground-cue-capabilities',
    ],
  },
  {
    id: 'T05',
    title: 'Fly the first leg with real predictions',
    route: '/missions',
    target: 'mission-simulation',
    guide: 'flight-predictions',
    outcomes: [
      'first-leg-replay',
      'first-leg-model-sources',
      'future-next-with-overdue',
      'unavailable-model-inputs',
    ],
    manual: ['prediction-advisory-semantics'],
  },
  {
    id: 'T06',
    title: 'Report applied transport and independent service checks',
    route: '/operator',
    target: 'transport',
    guide: 'transport',
    outcomes: [
      'applied-only-report',
      'independent-service-checks',
      'replacement-invalidates-checks',
      'transport-correction',
    ],
    manual: [],
  },
  {
    id: 'T07',
    title: 'Manage issues, capability and historical correction',
    route: '/operator',
    target: 'issues',
    guide: 'issues-capability',
    outcomes: [
      'issue-monitor-resolve-reopen',
      'issue-followup-cleared',
      'issue-historical-correction',
      'capability-independent',
    ],
    manual: [],
  },
  {
    id: 'T08',
    title: 'Retain notes and recover uncertain commands',
    route: '/operator',
    target: 'notes',
    guide: 'drafts-recovery',
    outcomes: [
      'scoped-note',
      'draft-switch-retained',
      'lost-receipt-same-key',
      'real-conflict-reconciled',
      'offline-draft-retained',
      'private-backup-restored',
    ],
    manual: [],
  },
  {
    id: 'T09',
    title: 'Record the ground gap and fly the second leg',
    route: '/missions',
    target: 'mission-simulation',
    guide: 'ground-gap',
    outcomes: [
      'between-legs-note',
      'second-leg-replay',
      'second-leg-model-sources',
      'stable-journal-across-legs',
      'restart-preserved-records',
    ],
    manual: ['replay-restart-limits'],
  },
  {
    id: 'T10',
    title: 'Prepare, export and import the original mission ZIP',
    route: '/missions',
    target: 'mission-export',
    guide: 'archive-transfer',
    outcomes: [
      'export-downloaded',
      'archive-contents-validated',
      'archive-imported-isolated',
      'export-cancel-recovery',
    ],
    manual: ['pdf-extracted-reviewed', 'export-failure-observed'],
  },
  {
    id: 'T11',
    title: 'Complete remaining field and recovery branches',
    route: '/operator',
    target: 'history',
    guide: 'parity-recovery',
    outcomes: [
      'immutable-history-complete',
      'storage-unavailable-recovery',
      'epoch-change-quarantine',
      'optional-provider-branches',
    ],
    manual: [
      'provider-states-understood',
      'field-checklist-reviewed',
      'quick-reference-used',
    ],
  },
] as const;
export type TrainingStageId = (typeof trainingSteps)[number]['id'];
export interface TrainingEvidence {
  providerStates?: readonly TrainingProviderState[];
  available: boolean;
  fresh: boolean;
  /** Produced by adapters over existing service responses; never persisted progress. */
  outcomes: readonly string[];
  historicalOutcomes?: readonly string[];
  toolingOutcomes?: readonly string[];
}
export interface StepEvaluation {
  status: 'passed' | 'skipped' | 'incomplete' | 'unavailable';
  missing: string[];
  manualOutcomes: string[];
  historicalOutcomes?: readonly string[];
  toolingOutcomes?: readonly string[];
}
export function evaluateStep(
  id: TrainingStageId,
  evidence: TrainingEvidence,
  progress?: TrainingProgress
): StepEvaluation {
  const step = trainingSteps.find((candidate) => candidate.id === id)!;
  const manualOutcomes = step.manual.filter((outcome) =>
    progress?.manualEvidence.some(
      (item) =>
        item.outcomeId === outcome &&
        item.note.trim() &&
        Number.isFinite(Date.parse(item.observedAt))
    )
  );
  const missing: string[] = [
    ...step.outcomes.filter(
      (outcome) =>
        !evidence.available ||
        !evidence.fresh ||
        !evidence.outcomes.includes(outcome)
    ),
    ...step.manual.filter((outcome) => !manualOutcomes.includes(outcome)),
  ];
  return {
    status:
      !evidence.available || !evidence.fresh
        ? 'unavailable'
        : progress?.skipped.includes(id)
          ? 'skipped'
          : missing.length
            ? 'incomplete'
            : 'passed',
    missing,
    manualOutcomes,
    toolingOutcomes: evidence.toolingOutcomes?.filter(
      (outcome) => !missing.includes(outcome)
    ),
    historicalOutcomes: evidence.historicalOutcomes?.filter(
      (outcome) => !missing.includes(outcome)
    ),
  };
}
