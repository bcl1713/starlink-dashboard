import type {
  OverviewDataSnapshot,
  OverviewSourceSlot,
} from '../overview-data-types';
import { OPERATIONAL_LAYERS } from './operational-map-contract';
import type {
  OperationalFeature,
  OperationalLayerState,
} from './operational-map-types';

export function buildLayerStates(
  snapshot: OverviewDataSnapshot,
  features: readonly OperationalFeature[]
): readonly OperationalLayerState[] {
  return OPERATIONAL_LAYERS.map((layer) =>
    buildLayerState(layer.id, sourceSlotForLayer(snapshot, layer.id), features)
  );
}

function buildLayerState(
  id: OperationalLayerState['id'],
  slot: OverviewSourceSlot<unknown>,
  features: readonly OperationalFeature[]
): OperationalLayerState {
  const retained = slot.data !== undefined && slot.phase !== 'ready';
  return {
    id,
    visible: true,
    phase: slot.phase,
    count:
      id === 'weather-radar'
        ? slot.data === undefined
          ? 0
          : 1
        : features.filter((feature) => feature.layerId === id).length,
    sourceTimestamp: slot.sourceTimestamp,
    retainedLastGood: retained,
    message:
      retained && slot.error
        ? `${slot.error.message} Showing retained last-good data.`
        : sourceMessage(slot),
  };
}

function sourceSlotForLayer(
  snapshot: OverviewDataSnapshot,
  id: OperationalLayerState['id']
): OverviewSourceSlot<unknown> {
  if (id.startsWith('planned-route')) return snapshot.route;
  if (id.startsWith('active-x-band')) return snapshot.activeLink;
  if (id.startsWith('position-history')) return snapshot.history;
  if (id === 'flight-route-markers') return snapshot.pois;
  if (id === 'satellites') return snapshot.satellites;
  if (id === 'mission-events') return snapshot.missionEvents;
  if (id === 'ground-entry-point-layer') return snapshot.groundEntryPoint;
  if (id === 'current-position-layer') return snapshot.telemetry;
  return snapshot.radar;
}

function sourceMessage(slot: OverviewSourceSlot<unknown>): string {
  if (slot.error) return slot.error.message;
  if (slot.phase === 'ready') return 'Ready.';
  if (slot.phase === 'initial-loading') return 'Loading.';
  return slot.phase;
}
