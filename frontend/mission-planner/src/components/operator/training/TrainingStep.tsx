import type { StepEvaluation, TrainingStageId } from './trainingSteps';
import { trainingSteps } from './trainingSteps';

const instructions: Record<TrainingStageId, string> = {
  T01: 'Select Fictional Meridian 21. Identify the mission, both named legs, UTC clock, reported connected customers and next future preparation. Keep an unsent note open while inspecting context; changing the mission must not move its target.',
  T02: 'Use Create call and Record completed call. Exercise a planned time, unknown actual timing, zero preparation lead, duration and a reschedule. Cancel and reinstate a call, then remove and restore its record. Inspect the immutable versions in History.',
  T03: 'Create a conference record, report it established and verify it. Report independent customers joining and leaving, including overlapping activity. Interrupt and restore the connection, then resume a customer as a new interval. Reuse the conference for another call and close it while a customer remains reported connected; inspect the discrepancy. These actions report operations; they do not provision a telecom bridge.',
  T04: 'Open Display tools and a training Overview window. Try recenter, display groups, presets, history and boundaries. Inspect supported foreground sound/notification controls and acknowledge a current occurrence. Report unsupported browser capabilities honestly; do not infer successful display movement from clicking a button.',
  T05: 'In Missions, preview and start the first leg at 1×. Use the documented local checkpoint command to advance synthetic inputs. Return to Operator and identify the next future preparation alongside overdue activity and X, Ka and PoP advisories. Inspect source freshness and current-leg alignment. Unknown PoP is not a reported outage.',
  T06: 'During customer activity, record an applied transport without inventing an intended or requested stage. Report service checks independently. Change a reported application and verify that the earlier check is no longer current; add a replacement check. Review the historical correction and advisory context.',
  T07: 'Create an issue, add mitigation and follow-up, monitor it, resolve it and reopen it. Clear follow-up and inspect the activity. Correct an earlier issue message without repeating its lifecycle transition. Record a separate capability assessment; it does not replace the issue or prove actual routing.',
  T08: 'Create an observation and notes with their original scope and unknown or approximate times. Park a draft, change mission/leg and resume it. Use the private exercise instructions for offline saving, a lost receipt, an actual second-client conflict and backup/restore. For a lost receipt, keep the draft and check guide evidence while the save is uncertain, before retrying. Then retry the original command and check evidence again. The guide requires the committed backend version observed before that retry.',
  T09: 'Record a ground-gap note with the previous and next named legs. Preview and start the return leg normally in Missions. Verify the new actual replay run and current-leg model sources while the same journal retains first-leg records. Restart the private instance and revalidate records. Restarting an expired replay segment does not restore an exact frame.',
  T10: 'Finish the mission and use its existing Export workflow to download the single mission ZIP. Inspect its original briefing PDF, journal/history, telemetry and checksums. Use the separate temporary import destination and verify its existing Operator records are unchanged. Exercise export preparation, cancellation and failure recovery; only confirm PDF review after opening the actual extracted file.',
  T11: 'Finish the field and recovery checklist in the guide: original scopes, immutable revisions, removed records, full history pagination, optional providers, unavailable storage, changed store epoch and retained commands. Use the quick reference. Incomplete or skipped branches remain visible; they are required before release acceptance.',
};
export function TrainingStep({
  stageId,
  evaluation,
}: {
  stageId: TrainingStageId;
  evaluation: StepEvaluation;
}) {
  const step = trainingSteps.find((item) => item.id === stageId)!;
  const status = {
    passed: 'Passed',
    skipped: 'Skipped',
    incomplete: 'Incomplete',
    unavailable: 'Evidence unavailable',
  }[evaluation.status];
  return (
    <section aria-labelledby="training-step-title" className="space-y-3">
      <h2 id="training-step-title">
        {step.id} · {step.title}
      </h2>
      <p role="status">{status}</p>
      <p>{instructions[stageId]}</p>
      <a
        className="ws-button inline-flex items-center"
        href={`/operator-help/guide.html#${step.guide}`}
        target="_blank"
        rel="noreferrer"
      >
        Read this procedure
      </a>
      <ul
        aria-label="Lesson outcome evidence"
        className="list-disc space-y-1 pl-5"
      >
        {[...step.outcomes, ...step.manual].map((outcome) => (
          <li key={outcome}>
            {outcome.replaceAll('-', ' ')} ·{' '}
            {evaluation.missing.includes(outcome)
              ? 'Needs evidence'
              : evaluation.manualOutcomes.includes(outcome)
                ? 'Human observation'
                : evaluation.historicalOutcomes?.includes(outcome)
                  ? 'Verified from retained source observation'
                  : 'Verified from current data'}
          </li>
        ))}
      </ul>
      {evaluation.missing.length > 0 && (
        <p>
          {evaluation.missing.length} required outcomes still need evidence.
        </p>
      )}
      {evaluation.manualOutcomes.length > 0 && (
        <p>
          {evaluation.manualOutcomes.length} explicitly recorded human
          observations. These are separate from journal evidence.
        </p>
      )}
    </section>
  );
}
