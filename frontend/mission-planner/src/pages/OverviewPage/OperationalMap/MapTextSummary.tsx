import {
  ARCGIS_WORLD_IMAGERY_ATTRIBUTION,
  OPERATIONAL_LAYERS,
  RADAR_ATTRIBUTION,
} from './operational-map-contract';
import type {
  BasemapStatus,
  OperationalFeature,
  OperationalLayerState,
  OperationalLayerVisibility,
} from './operational-map-types';

export function MapTextSummary({
  states,
  visibility,
  selectedFeature,
  measurementText,
  basemapStatus,
}: {
  readonly states: readonly OperationalLayerState[];
  readonly visibility: OperationalLayerVisibility;
  readonly selectedFeature: OperationalFeature | null;
  readonly measurementText: string;
  readonly basemapStatus: BasemapStatus;
}) {
  const byId = new Map(states.map((state) => [state.id, state]));
  return (
    <section className="operational-map__panel operational-map__summary">
      <h3>Operational map textual equivalent</h3>
      <p>
        Basemap: {basemapStatus.phase}. {basemapStatus.message}
      </p>
      <p>Basemap attribution: {ARCGIS_WORLD_IMAGERY_ATTRIBUTION}</p>
      <p>Radar: {RADAR_ATTRIBUTION}</p>
      <ul>
        {OPERATIONAL_LAYERS.map((layer) => {
          const state = byId.get(layer.id);
          return (
            <li key={layer.id}>
              {layer.label}: {visibility[layer.id] ? 'visible' : 'hidden'},{' '}
              {state?.phase ?? 'unavailable'}, {state?.count ?? 0} features,{' '}
              {state?.sourceTimestamp ?? 'unknown time'}, {state?.message}
            </li>
          );
        })}
      </ul>
      <p>{measurementText}</p>
      {selectedFeature ? (
        <div>
          <p>Selected: {selectedFeature.label}</p>
          <ul>
            {selectedFeature.details.map((detail) => (
              <li key={`${detail.label}:${detail.value}`}>
                {detail.label}: {detail.value}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
