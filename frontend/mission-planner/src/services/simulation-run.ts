import { z } from 'zod';
import { apiClient } from './api-client';
import { replayRouteSchema } from './simulation-run-route';

const timestamp = z.iso.datetime({ offset: true });
const id = z.string().min(1);
const number = z.number().finite();
const rate = number.min(0.1).max(1000);
export const pacingSchema = z.discriminatedUnion('mode', [
  z.object({ mode: z.literal('multiplier'), multiplier: rate }).strict(),
  z
    .object({
      mode: z.literal('target_runtime'),
      runtime_seconds: number.min(1),
    })
    .strict(),
]);
const normalized = {
  pacing: pacingSchema,
  effective_multiplier: rate,
  flight_duration_seconds: number.positive(),
  expected_runtime_seconds: number.positive(),
};
const planned = {
  ...normalized,
  plan_token: z.string().regex(/^[0-9a-f]{64}$/),
  planned_departure: timestamp,
  planned_arrival: timestamp,
};
const previewSchema = z
  .object({
    ...planned,
    limits: z
      .object({
        min_multiplier: z.literal(0.1),
        max_multiplier: z.literal(1000),
        min_runtime_seconds: z.literal(1),
      })
      .strict(),
  })
  .strict()
  .refine(validPlan, 'Inconsistent pacing or plan timing');
type PlanFields = z.infer<z.ZodObject<typeof planned>>;
function validPlan(plan: PlanFields) {
  const duration =
    (Date.parse(plan.planned_arrival) - Date.parse(plan.planned_departure)) /
    1000;
  const equal = (a: number, b: number) =>
    Math.abs(a - b) <= Math.max(1e-6, Math.abs(a) * 1e-6);
  return (
    equal(duration, plan.flight_duration_seconds) &&
    equal(
      duration / plan.effective_multiplier,
      plan.expected_runtime_seconds
    ) &&
    (plan.pacing.mode === 'multiplier'
      ? equal(plan.pacing.multiplier, plan.effective_multiplier)
      : equal(plan.pacing.runtime_seconds, plan.expected_runtime_seconds))
  );
}
const runSchema = z
  .object({
    ...planned,
    run_id: id,
    mission_id: id,
    leg_id: id,
    route_id: id,
    simulation_time: timestamp,
    started_at: timestamp,
    observed_at: timestamp,
    finished_at: timestamp.nullable(),
    elapsed_real_seconds: number.nonnegative(),
    completion_lateness_seconds: number.nonnegative().nullable(),
    progress_percent: number.min(0).max(100),
    phase: z.enum(['in_flight', 'post_arrival']),
    processed_event_count: z.number().int().nonnegative(),
    transport_states: z.record(
      z.string(),
      z.enum(['available', 'degraded', 'offline'])
    ),
    error: z.object({ code: id, message: id }).strict().nullable(),
  })
  .strict()
  .refine(validPlan, 'Inconsistent pacing or plan timing')
  .refine((run) => {
    const current = Date.parse(run.simulation_time),
      start = Date.parse(run.planned_departure),
      end = Date.parse(run.planned_arrival);
    return (
      current >= start &&
      current <= end &&
      Math.abs(
        run.progress_percent - ((current - start) / (end - start)) * 100
      ) < 1e-4 &&
      (run.phase === 'post_arrival' ? current === end : current < end)
    );
  }, 'Inconsistent simulation phase or progress');
export const simulationRunSchema = z
  .object({
    runtime_id: id,
    revision: z.number().int().nonnegative(),
    service_mode: z.enum(['simulation', 'live']),
    state: z.enum(['idle', 'running', 'completed', 'cancelled', 'failed']),
    served_at: timestamp,
    run: runSchema.nullable(),
  })
  .strict()
  .refine((status) => {
    if (status.state === 'idle') return status.run === null;
    if (!status.run) return false;
    if (status.state === 'running')
      return (
        status.service_mode === 'simulation' &&
        status.run.phase === 'in_flight' &&
        status.run.finished_at === null &&
        status.run.error === null
      );
    if (status.run.finished_at === null) return false;
    if (status.state === 'completed')
      return (
        status.run.phase === 'post_arrival' &&
        status.run.progress_percent === 100 &&
        status.run.completion_lateness_seconds !== null &&
        status.run.error === null
      );
    return status.state !== 'failed' || status.run.error !== null;
  }, 'Inconsistent run state');
export const missionTimeSchema = z
  .object({
    runtime_id: id,
    run_id: id,
    revision: z.number().int().nonnegative(),
    simulation_time: timestamp,
    observed_at: timestamp,
    phase: z.enum(['in_flight', 'post_arrival']),
    effective_multiplier: rate,
  })
  .strict();
export type PacingInput = z.infer<typeof pacingSchema>;
export type SimulationPreview = z.infer<typeof previewSchema>;
export type SimulationRunStatus = z.infer<typeof simulationRunSchema>;
export type MissionTimeContext = z.infer<typeof missionTimeSchema>;
const receivedTimes = new WeakMap<SimulationRunStatus, number>();
export function parseSimulationRun(data: unknown): SimulationRunStatus {
  const status = simulationRunSchema.parse(data);
  receivedTimes.set(status, performance.now());
  return status;
}
export function runReceivedAt(status: SimulationRunStatus | undefined) {
  return status ? receivedTimes.get(status) : undefined;
}
export interface SimulationStart {
  pacing: PacingInput;
  plan_token: string;
}
export const simulationRunApi = {
  async get(signal?: AbortSignal): Promise<SimulationRunStatus> {
    const response = await apiClient.get('/api/simulation/run', { signal });
    return parseSimulationRun(response.data);
  },
  async preview(
    missionId: string,
    legId: string,
    pacing: PacingInput,
    signal?: AbortSignal
  ): Promise<SimulationPreview> {
    const response = await apiClient.post(
      `/api/v2/missions/${missionId}/legs/${legId}/simulation/preview`,
      pacingSchema.parse(pacing),
      { signal }
    );
    return previewSchema.parse(response.data);
  },
  async route(runId: string, signal?: AbortSignal) {
    const response = await apiClient.get(`/api/simulation/run/${runId}/route`, {
      signal,
    });
    return replayRouteSchema.parse(response.data);
  },
};
