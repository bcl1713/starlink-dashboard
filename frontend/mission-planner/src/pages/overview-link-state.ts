import type { OverviewLinkSettings } from '../services/overview-link-settings';
import type { StatusResponse } from '../services/status';
import {
  measuredTrafficFlowEmitters,
  xBandFlowEmitters,
  type FlowEmitters,
  type LinkTelemetry,
} from './overview-flow-consumers';
import { isStatusStale } from './status-freshness';
import { projectAircraftScenePosition } from './x-band-active-link-projection';

export interface OverviewLinkStateInput {
  settings: OverviewLinkSettings | undefined;
  status: StatusResponse | undefined;
  nowMs: number;
  statusRequestFailed: boolean;
  hasTrafficGeometry: boolean;
  hasXBandGeometry: boolean;
  selectionState: 'normal' | 'warning' | null;
  selectionRequestFailed: boolean;
}

export interface OverviewLinkState {
  starshieldVisible: boolean;
  xBandVisible: boolean;
  starshieldFlow: FlowEmitters;
  xBandFlow: FlowEmitters;
}

/** Match readout provenance without substituting missing source observations. */
function availableMetric(
  status: StatusResponse | undefined,
  field: keyof LinkTelemetry
): number | undefined {
  const value = status?.network?.[field];
  return status?.metric_availability?.[field] === true &&
    typeof value === 'number' &&
    Number.isFinite(value)
    ? value
    : undefined;
}

/** Independent presentation policies; operational telemetry/state is read only. */
export function deriveOverviewLinkState(
  input: OverviewLinkStateInput
): OverviewLinkState {
  const { settings, status } = input;
  const aircraft = projectAircraftScenePosition(status);
  const freshPosition = Boolean(
    aircraft &&
      aircraft.position.every(Number.isFinite) &&
      typeof status?.timestamp === 'string' &&
      !input.statusRequestFailed &&
      !isStatusStale(status.timestamp, input.nowMs)
  );
  const starshieldVisible = Boolean(
    settings?.starshield_link_enabled &&
      freshPosition &&
      input.hasTrafficGeometry
  );
  // Retain the existing configured line/warning geometry while cached. Only
  // activity requires fresh position and an available current normal selection.
  const xBandVisible = Boolean(
    settings?.x_band_link_enabled && input.hasXBandGeometry
  );

  return {
    starshieldVisible,
    xBandVisible,
    starshieldFlow: measuredTrafficFlowEmitters(
      starshieldVisible
        ? {
            throughput_up_mbps: availableMetric(status, 'throughput_up_mbps'),
            throughput_down_mbps: availableMetric(
              status,
              'throughput_down_mbps'
            ),
            latency_ms: availableMetric(status, 'latency_ms'),
            packet_loss_percent: availableMetric(status, 'packet_loss_percent'),
          }
        : undefined
    ),
    xBandFlow: xBandFlowEmitters(
      xBandVisible &&
        freshPosition &&
        input.selectionState === 'normal' &&
        !input.selectionRequestFailed
    ),
  };
}
