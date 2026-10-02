import { projectActiveConfiguredXBandSatelliteId } from './x-band-active-link-projection';

export type PlannedSatelliteState =
  | { kind: 'selected'; satelliteId: string }
  | { kind: 'none' | 'loading' | 'unavailable' };

/** Selection is planning data, independent of telemetry freshness and geometry. */
export function derivePlannedSatelliteState(
  selection: unknown,
  isLoading: boolean,
  isError: boolean
): PlannedSatelliteState {
  if (isError) return { kind: 'unavailable' };
  if (isLoading) return { kind: 'loading' };
  const satelliteId = projectActiveConfiguredXBandSatelliteId(selection);
  if (satelliteId) return { kind: 'selected', satelliteId };
  if (
    typeof selection === 'object' &&
    selection !== null &&
    'satellite_id' in selection &&
    selection.satellite_id === null
  )
    return { kind: 'none' };
  return { kind: 'unavailable' };
}
