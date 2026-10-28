import type { OperatingContext } from '@/components/operator/workspace/operatingContext';
import type { OperatorHealth } from '@/types/operator';
import type { EventSnapshot, SourceCapture } from '@/types/operatorEvents';

export interface OverviewAdvisoryContext {
  missionId: string;
  legId: string;
  storeId: string;
  apiEpoch: string;
  sourceMode: 'live' | 'simulation';
  sourceIdentity: string | null;
  missionJournal: boolean;
  operatingContextId: string | null;
  replayRunId: string | null;
}
export interface OverviewAdvisoryClock {
  sourceMode: 'live' | 'simulation' | null;
  runId: string | null;
  missionId: string | null;
  legId: string | null;
  available: boolean;
}
export interface OverviewAdvisoryState {
  items: { id: string; title: string; detail: string }[];
  notice:
    | 'Transport Advisories Unavailable'
    | 'Transport Advisories Stale'
    | null;
}

export function overviewAdvisoryContext(
  active?: OperatingContext,
  health?: OperatorHealth
): OverviewAdvisoryContext | null {
  if (
    active?.state !== 'available' ||
    !active.mission_id ||
    !active.leg_id ||
    !health?.enabled ||
    !health.ready ||
    !health.store_id ||
    !health.api_epoch ||
    health.clock_regression ||
    active.source_mode !== health.source_mode ||
    (health.mission_journal &&
      (active.replay_run_id !== (health.replay_run_id ?? null) ||
        (active.operating_context_id ?? null) !==
          (health.operating_context_id ?? null)))
  )
    return null;
  return {
    missionId: active.mission_id,
    legId: active.leg_id,
    storeId: health.store_id,
    apiEpoch: health.api_epoch,
    sourceMode: health.source_mode,
    sourceIdentity: health.mission_journal
      ? (health.operating_context_id ??
        health.replay_run_id ??
        `idle:${health.simulation_run_id}`)
      : health.simulation_run_id,
    missionJournal: !!health.mission_journal,
    operatingContextId: health.operating_context_id ?? null,
    replayRunId: health.replay_run_id ?? null,
  };
}

export function snapshotMatchesOverviewContext(
  snapshot: EventSnapshot,
  context: OverviewAdvisoryContext
) {
  return (
    snapshot.schema_version === 1 &&
    snapshot.mission_id === context.missionId &&
    snapshot.store_id === context.storeId &&
    snapshot.api_epoch === context.apiEpoch &&
    snapshot.source_mode === context.sourceMode &&
    snapshot.simulation_run_id === context.sourceIdentity &&
    snapshot.cursor === null &&
    snapshot.truncated === false
  );
}

/** Presentation only: backend predicts, classifies, times, retires and acknowledges. */
export function deriveOverviewAdvisories({
  snapshot,
  context,
  missionNowMs,
  clock,
  receivedAgeMs,
  visible,
  failed,
}: {
  snapshot?: EventSnapshot;
  context: OverviewAdvisoryContext | null;
  missionNowMs: number;
  clock: OverviewAdvisoryClock;
  receivedAgeMs: number;
  visible: boolean;
  failed: boolean;
}): OverviewAdvisoryState {
  const unavailable: OverviewAdvisoryState = {
    items: [],
    notice: 'Transport Advisories Unavailable',
  };
  if (
    failed ||
    !snapshot ||
    !context ||
    !clock.available ||
    clock.sourceMode !== context.sourceMode ||
    (clock.sourceMode === 'live'
      ? clock.runId !== null || context.replayRunId !== null
      : clock.runId !== context.replayRunId ||
        clock.missionId !== context.missionId ||
        clock.legId !== context.legId) ||
    !Number.isFinite(missionNowMs) ||
    !snapshotMatchesOverviewContext(snapshot, context)
  )
    return unavailable;
  if (
    !Number.isFinite(receivedAgeMs) ||
    receivedAgeMs < 0 ||
    receivedAgeMs > (visible ? 45_000 : 150_000)
  )
    return { items: [], notice: 'Transport Advisories Stale' };
  // The feed covers the whole mission; Overview covers only the active leg.
  // Keep shared authority and every active-leg dependency (including PoP and
  // prerequisites). An unprepared future leg cannot invalidate this display.
  const activeSource = `model:${context.legId}`;
  const relevant = (source: SourceCapture) =>
    !source.source.startsWith('model:') ||
    source.source === activeSource ||
    source.source.startsWith(`${activeSource}:`);
  const available = (source: SourceCapture) =>
    source.freshness === 'disabled' ||
    (source.freshness === 'fresh' && source.aligned);
  const sources = snapshot.sources.filter(relevant);
  const explainedPartial =
    snapshot.coverage === 'partial' &&
    snapshot.sources.some((source) => !relevant(source) && !available(source));
  const view: OverviewAdvisoryState = {
    items: [],
    notice:
      (snapshot.coverage === 'available' || explainedPartial) &&
      sources.some((source) => source.source === activeSource) &&
      sources.every(available)
        ? null
        : unavailable.notice,
  };
  for (const event of snapshot.events) {
    if (
      event.mission_id !== context.missionId ||
      event.leg_id !== context.legId ||
      (context.missionJournal &&
        ((event.operating_context_id ?? null) !== context.operatingContextId ||
          (event.replay_run_id ?? null) !== context.replayRunId))
    )
      continue;
    const pop =
      event.kind === 'pop_advisory' &&
      event.advisory_type === 'transition_window';
    if (!pop && event.kind !== 'restriction') continue;
    if (
      event.provenance !== 'modeled' ||
      !event.active ||
      event.notification.retired ||
      event.notification.acknowledged
    )
      continue;
    const source = snapshot.sources.find((s) => s.source === event.source_ref);
    if (
      !source ||
      !source.aligned ||
      source.revision !== event.source_revision ||
      source.freshness !== 'fresh' ||
      event.freshness !== 'fresh' ||
      !event.notification.available ||
      !event.notification.generation ||
      event.notification.preview ||
      event.state === 'unknown'
    ) {
      view.notice = unavailable.notice;
      continue;
    }
    const start = Date.parse(event.due_at ?? '');
    const end = Date.parse(event.end_at ?? '');
    const threshold = Date.parse(event.notification.threshold_at ?? '');
    if (
      ![start, end, threshold].every(Number.isFinite) ||
      end <= start ||
      threshold > start
    ) {
      view.notice = unavailable.notice;
      continue;
    }
    if (missionNowMs < threshold || missionNowMs >= end) continue;
    // Titles are the server's explicit vocabulary; classification never inspects text.
    const phase = missionNowMs < start ? 'Approaching' : 'Current';
    const provenance =
      event.time_basis === 'planned_utc' ? 'Planned' : 'Modeled';
    view.items.push({
      id: `${event.event_id}:${event.notification.generation}:${event.notification.severity_generation}`,
      title: event.title,
      detail: pop
        ? `Brief Interruption Possible · ${provenance}`
        : `${phase} · ${provenance}`,
    });
  }
  return view;
}
