import 'leaflet/dist/leaflet.css';
import './operational-map.css';

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import L, { type Map as LeafletMap } from 'leaflet';
import { MapContainer } from 'react-leaflet';

import { createDefaultLayerVisibility } from './operational-map-contract';
import { buildFeatureBounds, finiteGeographic } from './operational-map-bounds';
import {
  buildOperationalFeatures,
  createHistoryIdRegistry,
} from './build-operational-features';
import type {
  OperationalFeature,
  OperationalMapHandle,
  OperationalMapProps,
} from './operational-map-types';
import { FeatureDetails } from './FeatureDetails';
import { LayerDisclosure } from './LayerDisclosure';
import { MapControls } from './MapControls';
import { MapTextSummary } from './MapTextSummary';
import { StableMapComposition } from './StableMapComposition';

export type { OperationalMapHandle } from './operational-map-types';

export const OperationalMap = forwardRef<
  OperationalMapHandle,
  OperationalMapProps
>(function OperationalMap(
  {
    snapshot,
    radarEnabled,
    radarRefreshToken,
    retryRadar,
    reportRadarResult,
    onRadarEnabledChange,
    initialLayerVisibility,
    onLayerVisibilityChange,
    onMapReady,
  },
  ref
) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dismissedMissingId, setDismissedMissingId] = useState<string | null>(
    null
  );
  const [measurePoints, setMeasurePoints] = useState<L.LatLng[]>([]);
  const [mobileLocked, setMobileLocked] = useState(false);
  const [mobileActive, setMobileActive] = useState(false);
  const activationButton = useRef<HTMLButtonElement | null>(null);
  const performedInitialFit = useRef(false);
  const readyMap = useRef<LeafletMap | null>(null);
  const [registry] = useState(createHistoryIdRegistry);
  const [visibility, setVisibility] = useState(
    initialLayerVisibility ?? createDefaultLayerVisibility(radarEnabled)
  );
  const { features, layerStates } = useMemo(
    () => buildOperationalFeatures(snapshot, registry),
    [registry, snapshot]
  );
  const selectedFeature =
    features.find((feature) => feature.id === selectedId) ?? null;
  const missingSelection =
    selectedId !== null &&
    selectedFeature === null &&
    dismissedMissingId !== selectedId;

  const fit = useCallback(() => {
    if (!map) return;
    const bounds = buildFeatureBounds(
      features.filter((feature) => visibility[feature.layerId])
    );
    if (!bounds) return;
    try {
      map.fitBounds(bounds, {
        animate: !prefersReducedMotion(),
        maxZoom: 8,
        padding: [24, 24],
      });
    } catch {
      // Leaflet can reject malformed container state during test teardown.
    }
  }, [features, map, visibility]);

  useImperativeHandle(
    ref,
    () => ({
      fitToAvailableLayers: fit,
      focusCoordinates(options) {
        if (
          !map ||
          options.zoom !== 8 ||
          !finiteGeographic(options.latitude, options.longitude)
        ) {
          return;
        }
        try {
          map.setView([options.latitude, options.longitude], 8, {
            animate:
              options.motion === 'reduced-aware' && !prefersReducedMotion(),
          });
        } catch {
          return;
        }
      },
      getMap: () => map,
    }),
    [fit, map]
  );

  useEffect(() => {
    if (!map || performedInitialFit.current || features.length === 0) return;
    performedInitialFit.current = true;
    fit();
  }, [features.length, fit, map]);

  useEffect(() => {
    const query = window.matchMedia?.('(min-width: 768px)');
    if (!query) return;
    const apply = () => {
      const locked = !query.matches;
      setMobileLocked(locked);
      if (!locked) setMobileActive(true);
      else setMobileActive(false);
    };
    apply();
    query.addEventListener('change', apply);
    return () => query.removeEventListener('change', apply);
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && mobileLocked && mobileActive) {
        activationButton.current?.focus();
        setMobileActive(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [mobileActive, mobileLocked]);

  const measurementText = buildMeasurementText(map, measurePoints);
  return (
    <section className="operational-map" aria-label="Operational map">
      <MapContainer
        center={[0, 0]}
        className="operational-map__canvas"
        ref={setMap}
        scrollWheelZoom={false}
        zoom={1}
      >
        <StableMapComposition
          features={features}
          mapRef={readyMap}
          mobileActive={mobileActive}
          mobileLocked={mobileLocked}
          onMapReady={onMapReady}
          onSelect={(id) => {
            setSelectedId(id);
            setDismissedMissingId(null);
          }}
          radarEnabled={radarEnabled}
          radarRefreshToken={radarRefreshToken}
          reportRadarResult={reportRadarResult}
          visibility={visibility}
        />
      </MapContainer>
      <div className="operational-map__overlay">
        <MapControls
          activationButtonRef={activationButton}
          measurementText={measurementText}
          mobileActive={mobileActive}
          mobileLocked={mobileLocked}
          onActivateMobile={() => setMobileActive(true)}
          onAddCenter={() => {
            if (map) setMeasurePoints((points) => [...points, map.getCenter()]);
          }}
          onClearMeasure={() => setMeasurePoints([])}
          onDisableMobile={() => {
            activationButton.current?.focus();
            setMobileActive(false);
          }}
          onFit={fit}
          onZoomIn={() => map?.zoomIn()}
          onZoomOut={() => map?.zoomOut()}
        />
        <LayerDisclosure
          radarEnabled={radarEnabled}
          retryRadar={retryRadar}
          states={layerStates.map((state) => ({
            ...state,
            visible: visibility[state.id],
          }))}
          visibility={{ ...visibility, 'weather-radar': radarEnabled }}
          onRadarEnabledChange={onRadarEnabledChange}
          onVisibilityChange={(next) => {
            setVisibility(next);
            onLayerVisibilityChange?.(next);
          }}
        />
        <FeatureButtons
          features={features}
          onSelect={(id) => {
            setSelectedId(id);
            setDismissedMissingId(null);
          }}
        />
        <FeatureDetails
          feature={selectedFeature}
          missing={missingSelection}
          onDismissMissing={() => setDismissedMissingId(selectedId)}
        />
        <MapTextSummary
          measurementText={measurementText}
          selectedFeature={selectedFeature}
          states={layerStates}
          visibility={{ ...visibility, 'weather-radar': radarEnabled }}
        />
      </div>
    </section>
  );
});

function FeatureButtons({
  features,
  onSelect,
}: {
  readonly features: readonly OperationalFeature[];
  readonly onSelect: (id: string) => void;
}) {
  return (
    <div className="operational-map__panel">
      {features.map((feature) => (
        <button
          key={feature.id}
          onClick={() => onSelect(feature.id)}
          type="button"
        >
          {feature.label}
        </button>
      ))}
    </div>
  );
}

function buildMeasurementText(
  map: LeafletMap | null,
  points: readonly L.LatLng[]
): string {
  if (!map || points.length < 2) return 'Measurement: no distance selected';
  let meters = 0;
  for (let index = 1; index < points.length; index += 1) {
    meters += map.distance(points[index - 1], points[index]);
  }
  return `Measurement: ${(meters / 1000).toFixed(1)} km`;
}

function prefersReducedMotion(): boolean {
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  );
}
