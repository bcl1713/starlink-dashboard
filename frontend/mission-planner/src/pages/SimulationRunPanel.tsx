import type { SimulationRunStatus } from '@/services/simulation-run';
import './SimulationRunPanel.css';
export function SimulationRunPanel({
  status,
  stale,
  compact,
}: {
  status: SimulationRunStatus | undefined;
  stale: boolean;
  compact: boolean;
}) {
  if (!status?.run || status.state === 'idle') return null;
  const run = status.run;
  return (
    <section
      className="simulation-run-panel"
      data-compact={compact}
      aria-label="Simulation run"
    >
      <strong>
        Simulation ·{' '}
        {status.state === 'running'
          ? 'Running'
          : status.state[0].toUpperCase() + status.state.slice(1)}{' '}
        · {run.effective_multiplier}×
      </strong>
      <progress
        aria-label="Simulated progress"
        value={run.progress_percent}
        max={100}
      />
      <span>
        {run.progress_percent.toFixed(1)}% ·{' '}
        {run.simulation_time.replace('T', ' ').replace('Z', ' UTC')} simulated
      </span>
      <span>
        {run.elapsed_real_seconds.toFixed(1)} /{' '}
        {run.expected_runtime_seconds.toFixed(1)} real seconds
      </span>
      {stale && (
        <span role="status">Refresh unavailable · simulated clock frozen</span>
      )}
      {run.error && <span role="alert">{run.error.message}</span>}
      {run.completion_lateness_seconds !== null && (
        <span>
          Completion lateness: {run.completion_lateness_seconds.toFixed(2)} real
          seconds
        </span>
      )}
    </section>
  );
}
