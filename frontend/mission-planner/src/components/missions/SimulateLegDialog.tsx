import { useEffect, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useActivateLeg } from '@/hooks/api/useMissions';
import { useSimulationRun } from '@/hooks/api/useSimulationRun';
import {
  pacingSchema,
  simulationRunApi,
  type SimulationPreview,
} from '@/services/simulation-run';

export function SimulateLegDialog({
  missionId,
  legId,
  open,
  onOpenChange,
}: {
  missionId: string;
  legId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [mode, setMode] = useState<'multiplier' | 'target_runtime'>(
    'multiplier'
  );
  const [multiplier, setMultiplier] = useState('10'),
    [runtime, setRuntime] = useState('120');
  const [preview, setPreview] = useState<SimulationPreview | null>(null);
  const identity = `${missionId}/${legId}/${open}`;
  const [draftIdentity, setDraftIdentity] = useState(identity);
  const [error, setError] = useState<string | null>(null),
    [pending, setPending] = useState(false);
  const generation = useRef(0),
    controller = useRef<AbortController | null>(null),
    starting = useRef(false);
  const run = useSimulationRun(),
    activation = useActivateLeg();
  const pacing =
    mode === 'multiplier'
      ? { mode, multiplier: Number(multiplier) }
      : { mode, runtime_seconds: Number(runtime) };
  const valid = pacingSchema.safeParse(pacing);
  const enabled = run.data?.service_mode === 'simulation';
  if (draftIdentity !== identity) {
    setDraftIdentity(identity);
    setPreview(null);
    setPending(false);
    setError(null);
  }
  useEffect(
    () => () => {
      generation.current++;
      controller.current?.abort();
    },
    [missionId, legId, open]
  );
  function invalidate() {
    generation.current++;
    controller.current?.abort();
    setPreview(null);
    setError(null);
    setPending(false);
  }
  async function requestPreview() {
    if (!enabled || !valid.success || pending || starting.current) return;
    const sequence = ++generation.current;
    controller.current?.abort();
    controller.current = new AbortController();
    setPending(true);
    setPreview(null);
    setError(null);
    try {
      const result = await simulationRunApi.preview(
        missionId,
        legId,
        valid.data,
        controller.current.signal
      );
      if (sequence === generation.current) setPreview(result);
    } catch (cause) {
      if (sequence === generation.current)
        setError(
          cause instanceof Error ? cause.message : 'Preview unavailable'
        );
    } finally {
      if (sequence === generation.current) setPending(false);
    }
  }
  async function start() {
    if (!preview || !valid.success || !enabled || starting.current) return;
    starting.current = true;
    setError(null);
    try {
      await activation.mutateAsync({
        missionId,
        legId,
        simulation: { pacing: valid.data, plan_token: preview.plan_token },
      });
      onOpenChange(false);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Simulation could not start'
      );
      setPreview(null);
    } finally {
      starting.current = false;
    }
  }
  const fieldError = valid.success
    ? null
    : mode === 'multiplier'
      ? 'Enter a multiplier from 0.1 to 1000.'
      : 'Enter at least 1 real second.';
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        invalidate();
        onOpenChange(value);
      }}
    >
      <DialogContent>
        <DialogTitle>Simulate leg</DialogTitle>
        <DialogDescription>
          Preview the planned flight, then start it on a shared simulated clock.
          Speeds remain the planned flight speeds.
        </DialogDescription>
        {!enabled && (
          <p role="status">
            {run.data?.service_mode === 'live'
              ? 'Simulation is unavailable in live mode.'
              : 'Waiting for confirmed service mode.'}
          </p>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (preview) void start();
            else void requestPreview();
          }}
        >
          <fieldset disabled={activation.isPending} className="grid gap-3">
            <legend>Pacing</legend>
            <label>
              <input
                type="radio"
                name="pacing"
                checked={mode === 'multiplier'}
                onChange={() => {
                  invalidate();
                  setMode('multiplier');
                }}
              />{' '}
              Multiplier mode
            </label>
            <label>
              <input
                type="radio"
                name="pacing"
                checked={mode === 'target_runtime'}
                onChange={() => {
                  invalidate();
                  setMode('target_runtime');
                }}
              />{' '}
              Target runtime
            </label>
            {mode === 'multiplier' ? (
              <>
                <label htmlFor="simulation-multiplier">Multiplier</label>
                <input
                  id="simulation-multiplier"
                  type="number"
                  min="0.1"
                  max="1000"
                  step="any"
                  value={multiplier}
                  aria-invalid={!valid.success}
                  aria-describedby={
                    fieldError ? 'simulation-field-error' : undefined
                  }
                  onChange={(event) => {
                    invalidate();
                    setMultiplier(event.target.value);
                  }}
                />
                <div className="flex gap-2">
                  {[1, 2, 10].map((rate) => (
                    <Button
                      key={rate}
                      type="button"
                      variant="outline"
                      onClick={() => {
                        invalidate();
                        setMultiplier(String(rate));
                      }}
                    >
                      {rate}×
                    </Button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <label htmlFor="simulation-runtime">Runtime seconds</label>
                <input
                  id="simulation-runtime"
                  type="number"
                  min="1"
                  step="any"
                  value={runtime}
                  aria-invalid={!valid.success}
                  aria-describedby={
                    fieldError ? 'simulation-field-error' : undefined
                  }
                  onChange={(event) => {
                    invalidate();
                    setRuntime(event.target.value);
                  }}
                />
              </>
            )}
            {fieldError && <p id="simulation-field-error">{fieldError}</p>}
            <Button
              type="button"
              onClick={() => void requestPreview()}
              disabled={!enabled || !valid.success || pending}
            >
              {pending ? 'Previewing…' : 'Preview'}
            </Button>
            {preview && (
              <div aria-label="Simulation preview">
                <p>
                  {preview.effective_multiplier}× ·{' '}
                  {preview.flight_duration_seconds.toFixed(1)} simulated seconds
                  · {preview.expected_runtime_seconds.toFixed(1)} real seconds
                </p>
                <p>
                  {preview.planned_departure} → {preview.planned_arrival}
                </p>
              </div>
            )}
            {error && <p role="alert">{error}</p>}
            <Button
              type="submit"
              disabled={!enabled || !preview || pending || activation.isPending}
            >
              {activation.isPending ? 'Starting…' : 'Start simulation'}
            </Button>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}
