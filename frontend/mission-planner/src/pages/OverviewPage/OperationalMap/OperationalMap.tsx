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
  BasemapStatus,
  OperationalMapHandle,
  OperationalMapProps,
} from './operational-map-types';
import { FeatureDetails } from './FeatureDetails';
import { FeatureButtons } from './FeatureButtons';
import { LayerDisclosure } from './LayerDisclosure';
import { MapControls } from './MapControls';
import { MapTextSummary } from './MapTextSummary';
import {
  buildMeasurementText,
  prefersReducedMotion,
} from './operational-map-helpers';
import { StableMapComposition } from './StableMapComposition';
import { useMeasurementLine } from './useMeasurementLine';

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
  const [measureMode, setMeasureMode] = useState(false);
  const [mobileLocked, setMobileLocked] = useState(false);
  const [mobileActive, setMobileActive] = useState(false);
  const [basemapStatus, setBasemapStatus] = useState<BasemapStatus>({
    phase: 'loading',
    message: 'Basemap tiles loading.',
  });
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

  const fit = useCallback((): boolean => {
    if (!map) return false;
    const bounds = buildFeatureBounds(
      features.filter((feature) => visibility[feature.layerId])
    );
    if (!bounds) return false;
    try {
      map.fitBounds(bounds, {
        animate: !prefersReducedMotion(),
        maxZoom: 8,
        padding: [24, 24],
      });
      return true;
    } catch {
      // Leaflet can reject malformed container state during test teardown.
      return false;
    }
  }, [features, map, visibility]);

  useImperativeHandle(
    ref,
    () => ({
      fitToAvailableLayers() {
        fit();
      },
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
    if (fit()) performedInitialFit.current = true;
  }, [features.length, fit, map]);

  useEffect(() => {
    if (!map || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      try {
        map.invalidateSize({ pan: false });
      } catch {
        return;
      }
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);

  useMeasurementLine(map, measurePoints);

  useEffect(() => {
    if (!map) return;
    const addPoint = (event: L.LeafletMouseEvent) => {
      setMeasurePoints((points) => [...points, event.latlng]);
    };
    if (measureMode) {
      map.dragging.disable();
      map.on('click', addPoint);
    }
    return () => {
      map.off('click', addPoint);
      if (!mobileLocked || mobileActive) map.dragging.enable();
    };
  }, [map, measureMode, mobileActive, mobileLocked]);

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
        zoomControl={false}
        zoom={1}
      >
        <StableMapComposition
          features={features}
          mapRef={readyMap}
          mobileActive={mobileActive}
          mobileLocked={mobileLocked}
          onMapReady={onMapReady}
          onBasemapStatusChange={setBasemapStatus}
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
          onToggleMeasure={() => setMeasureMode((enabled) => !enabled)}
          onUndoMeasure={() =>
            setMeasurePoints((points) => points.slice(0, -1))
          }
          onZoomIn={() => map?.zoomIn()}
          onZoomOut={() => map?.zoomOut()}
          measureMode={measureMode}
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
          basemapStatus={basemapStatus}
          measurementText={measurementText}
          selectedFeature={selectedFeature}
          states={layerStates}
          visibility={{ ...visibility, 'weather-radar': radarEnabled }}
        />
      </div>
    </section>
  );
});
