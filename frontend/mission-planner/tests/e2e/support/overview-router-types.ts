import type { OverviewScenario } from '../fixtures/overview';
import type { LatencyPayloadOverride } from './overview-payloads';
import type { OverviewScenarioId } from './overview-empty-scenario';

export interface RecordedOverviewRequest {
  readonly id: string;
  readonly cycle: number;
  readonly event: 'start' | 'complete' | 'error' | 'failed' | 'blocked';
  readonly kind: 'initial' | 'scheduled' | 'manual';
  readonly source: string;
  readonly method: string;
  readonly url: string;
  readonly status: number | null;
  readonly outcome: 'pending' | 'complete' | 'error' | 'transport-failed';
  readonly firstParty: boolean;
  readonly startedAt: number;
  readonly completedAt: number | null;
}

export interface OverviewRouter {
  readonly records: readonly RecordedOverviewRequest[];
  readonly cycles: readonly string[];
  scenario(): OverviewScenario;
  setScenario(id: OverviewScenarioId): void;
  setSourceScenario(source: string, id: OverviewScenarioId | null): void;
  failSourceOnce(source: string, status: number, detail: string): void;
  failNextBasemap(): void;
  setLatency(payload: LatencyPayloadOverride | null): void;
  markNextManualCycle(): void;
  setLifecycleReporter(
    reporter: ((record: RecordedOverviewRequest) => void) | null
  ): void;
}
