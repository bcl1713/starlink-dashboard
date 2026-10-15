import type { PlannedSatelliteState } from './overview-planned-satellite';
import './OverviewPlannedSatelliteCard.css';

/** A configured selection never asserts measured satellite connectivity. */
export function OverviewPlannedSatelliteCard({
  state,
}: {
  state: PlannedSatelliteState;
}) {
  const value =
    state.kind === 'selected'
      ? state.satelliteId
      : state.kind === 'none'
        ? 'NO SATELLITE SELECTED'
        : state.kind === 'loading'
          ? 'LOADING…'
          : 'UNAVAILABLE';
  return (
    <section
      className={`overview-planned-satellite overview-planned-satellite--${state.kind}${state.kind === 'selected' && state.satelliteId.length > 24 ? ' overview-planned-satellite--long-id' : ''}`}
      aria-label="Planned satellite"
    >
      <p className="overview-planned-satellite__label">X-BAND</p>
      <strong className="overview-planned-satellite__id">{value}</strong>
      <p className="overview-planned-satellite__label">PLANNED SATELLITE</p>
    </section>
  );
}
