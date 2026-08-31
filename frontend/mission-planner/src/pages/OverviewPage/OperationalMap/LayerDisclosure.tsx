import type {
  OperationalLayerState,
  OperationalLayerVisibility,
} from './operational-map-types';
import { OPERATIONAL_LAYERS } from './operational-map-contract';

interface LayerDisclosureProps {
  readonly states: readonly OperationalLayerState[];
  readonly visibility: OperationalLayerVisibility;
  readonly radarEnabled: boolean;
  readonly onVisibilityChange: (visibility: OperationalLayerVisibility) => void;
  readonly onRadarEnabledChange: (enabled: boolean) => void;
  readonly retryRadar: () => void;
}

export function LayerDisclosure({
  states,
  visibility,
  radarEnabled,
  onVisibilityChange,
  onRadarEnabledChange,
  retryRadar,
}: LayerDisclosureProps) {
  const stateById = new Map(states.map((state) => [state.id, state]));
  const radarFailed = stateById.get('weather-radar')?.phase === 'error';
  return (
    <details className="operational-map__panel" open>
      <summary className="operational-map__layer-summary">
        Operational layers
      </summary>
      <div className="operational-map__layers">
        {OPERATIONAL_LAYERS.map((layer) => {
          const checked =
            layer.id === 'weather-radar' ? radarEnabled : visibility[layer.id];
          return (
            <label className="operational-map__layer-row" key={layer.id}>
              <span>
                {layer.label}
                <small> {stateById.get(layer.id)?.message}</small>
              </span>
              <input
                aria-label={layer.label}
                checked={checked}
                className="operational-map__toggle"
                onChange={(event) => {
                  if (layer.id === 'weather-radar') {
                    onRadarEnabledChange(event.currentTarget.checked);
                    return;
                  }
                  onVisibilityChange({
                    ...visibility,
                    [layer.id]: event.currentTarget.checked,
                  });
                }}
                type="checkbox"
              />
            </label>
          );
        })}
      </div>
      {radarFailed ? (
        <button
          className="operational-map__button"
          onClick={retryRadar}
          type="button"
        >
          Retry weather radar
        </button>
      ) : null}
    </details>
  );
}
