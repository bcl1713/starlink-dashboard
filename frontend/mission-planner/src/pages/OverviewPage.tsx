import {
  useCallback,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';
import type { OverviewPOIFilter } from '../types/monitoring';
import {
  addOverviewClock,
  loadOverviewPreferences,
  moveOverviewClock,
  relabelOverviewClock,
  removeOverviewClock,
  saveOverviewPreferences,
  type OverviewPreferences,
  type OverviewRefreshCadence,
} from './OverviewPage/preferences';
import { useOverviewClock } from './OverviewPage/useOverviewClock';
import { useOverviewData } from './OverviewPage/useOverviewData';
import { OverviewControls } from './OverviewPage/OverviewControls';
import { OverviewClocks } from './OverviewPage/OverviewClocks';
import {
  OverviewGrid,
  useOverviewFullscreen,
} from './OverviewPage/OverviewGrid';
import {
  OperationalMap,
  type OperationalMapHandle,
} from './OverviewPage/OperationalMap';
import { NetworkLatencyPanel } from './OverviewPage/components/NetworkLatencyPanel';
import { ThroughputPanel } from './OverviewPage/components/ThroughputPanel';
import { PacketLossPanel } from './OverviewPage/components/PacketLossPanel';
import { ObstructionGauge } from './OverviewPage/components/ObstructionGauge';
import { GroundEntryPointPanel } from './OverviewPage/components/GroundEntryPointPanel';
import { POIQuickReference } from './OverviewPage/components/POIQuickReference';
import type { OverviewDataSnapshot } from './OverviewPage/overview-data-types';
import { classifyLatency, formatCoordinates } from './OverviewPage/formatters';

function updatePreferences(
  setPreferences: Dispatch<SetStateAction<OverviewPreferences>>,
  updater: (current: OverviewPreferences) => OverviewPreferences
) {
  setPreferences((current) => {
    const next = updater(current);
    saveOverviewPreferences(window.localStorage, next);
    return next;
  });
}

function prioritySummary(snapshot: OverviewDataSnapshot): string {
  const telemetry = snapshot.telemetry;
  const status = telemetry.data;
  const telemetryText = telemetry.paused
    ? `Paused - last updated ${telemetry.sourceTimestamp ?? 'unknown'}`
    : telemetry.freshness === 'fresh'
      ? 'Telemetry fresh'
      : telemetry.freshness === 'stale'
        ? 'Telemetry stale'
        : 'Telemetry unavailable';
  const routes = [
    snapshot.route.data?.west,
    snapshot.route.data?.east,
  ].filter((route) => route && route.total > 0);
  const routeText = routes[0]?.route_name
    ? `Active route ${routes[0].route_name}`
    : 'No active route';
  const positionText = status
    ? `Position ${formatCoordinates(
        status.position.latitude,
        status.position.longitude
      )}`
    : 'Position unavailable';
  const latency = classifyLatency(status?.network.latency_ms ?? null);
  return `${telemetryText}. ${routeText}. ${positionText}. Latency ${latency.label}.`;
}

export function OverviewPage() {
  const pageRef = useRef<HTMLDivElement | null>(null);
  const fullscreenButtonRef = useRef<HTMLButtonElement | null>(null);
  const operationalMapRef = useRef<OperationalMapHandle | null>(null);
  const [preferences, setPreferences] = useState(() =>
    loadOverviewPreferences(window.localStorage)
  );
  const now = useOverviewClock();
  const { snapshot, controller } = useOverviewData({
    cadence: preferences.refreshCadence,
    poiFilter: preferences.poiFilter,
    radarEnabled: preferences.radarEnabled,
  });
  const fullscreen = useOverviewFullscreen(pageRef, fullscreenButtonRef);
  const nowTimestamp = now.toISOString();

  const save = useCallback(
    (updater: (current: OverviewPreferences) => OverviewPreferences) =>
      updatePreferences(setPreferences, updater),
    []
  );
  const setCadence = useCallback(
    (refreshCadence: OverviewRefreshCadence) =>
      save((current) => ({ ...current, refreshCadence })),
    [save]
  );
  const setPoiFilter = useCallback(
    (poiFilter: OverviewPOIFilter) => save((current) => ({ ...current, poiFilter })),
    [save]
  );
  const setRadarEnabled = useCallback(
    (radarEnabled: boolean) => save((current) => ({ ...current, radarEnabled })),
    [save]
  );
  const setDisclosure = useCallback(
    (key: keyof OverviewPreferences['disclosures'], value: boolean) =>
      save((current) => ({
        ...current,
        disclosures: { ...current.disclosures, [key]: value },
      })),
    [save]
  );
  const focusGroundEntryPoint = useCallback(
    (coordinates: Readonly<{ latitude: number; longitude: number }>) => {
      operationalMapRef.current?.focusCoordinates({
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
        zoom: 8,
        motion: 'reduced-aware',
      });
    },
    []
  );

  return (
    <div
      ref={pageRef}
      className={`overview-page overview-page--${fullscreen.mode}`}
      tabIndex={-1}
      aria-labelledby="overview-title"
    >
      <header className="overview-header">
        <div className="overview-header__copy">
          <h1 id="overview-title" tabIndex={-1}>
            Operations Overview
          </h1>
          <p className="overview-priority-summary">
            {prioritySummary(snapshot)}
          </p>
        </div>
        <div className="overview-header__actions">
          <OverviewControls
            preferences={preferences}
            manualRefreshPending={controller.isManualRefreshPending}
            onRefreshCadenceChange={setCadence}
            onManualRefresh={controller.manualRefresh}
            onPOIFilterChange={setPoiFilter}
            onControlsExpandedChange={(expanded) =>
              setDisclosure('controlsExpanded', expanded)
            }
            onClockSettingsExpandedChange={(expanded) =>
              setDisclosure('clockSettingsExpanded', expanded)
            }
            onAddClock={(input) =>
              save((current) => addOverviewClock(current, input))
            }
            onRelabelClock={(id, label) =>
              save((current) => relabelOverviewClock(current, id, label))
            }
            onMoveClock={(id, direction) =>
              save((current) => moveOverviewClock(current, id, direction))
            }
            onRemoveClock={(id) =>
              save((current) => removeOverviewClock(current, id))
            }
          />
          <button
            ref={fullscreenButtonRef}
            type="button"
            className="overview-fullscreen-button"
            aria-describedby={
              fullscreen.fallbackMessage ? 'overview-fullscreen-message' : undefined
            }
            onClick={() => {
              void (fullscreen.mode === 'inline'
                ? fullscreen.enterFromUserGesture()
                : fullscreen.exitFromUserGesture());
            }}
          >
            {fullscreen.mode === 'inline' ? (
              <Maximize2 aria-hidden="true" />
            ) : (
              <Minimize2 aria-hidden="true" />
            )}
            <span>
              {fullscreen.mode === 'inline' ? 'Enter fullscreen' : 'Exit fullscreen'}
            </span>
          </button>
          {fullscreen.fallbackMessage ? (
            <p id="overview-fullscreen-message">{fullscreen.fallbackMessage}</p>
          ) : null}
        </div>
      </header>
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {snapshot.announcement ?? ''}
      </p>
      <section
        className="overview-world-clocks"
        aria-labelledby="world-clocks-heading"
      >
        <h2 id="world-clocks-heading">World clocks</h2>
        <OverviewClocks
          clocks={preferences.clocks}
          now={now}
          expanded={preferences.disclosures.additionalClocksExpanded}
          onExpandedChange={(expanded) =>
            setDisclosure('additionalClocksExpanded', expanded)
          }
        />
      </section>
      <OverviewGrid
        map={
          <OperationalMap
            ref={operationalMapRef}
            snapshot={snapshot}
            radarEnabled={preferences.radarEnabled}
            radarRefreshToken={controller.radarRefreshToken}
            retryRadar={controller.retryRadar}
            reportRadarResult={controller.reportRadarResult}
            onRadarEnabledChange={setRadarEnabled}
          />
        }
        groundEntryPoint={
          <GroundEntryPointPanel
            slot={snapshot.groundEntryPoint}
            retryPending={snapshot.groundEntryPoint.pending}
            onRetry={controller.manualRefresh}
            headingAs="h3"
            onFocusCoordinates={focusGroundEntryPoint}
          />
        }
        obstruction={
          <ObstructionGauge
            slot={snapshot.telemetry}
            retryPending={snapshot.telemetry.pending}
            onRetry={controller.manualRefresh}
            headingAs="h3"
          />
        }
        packetLoss={
          <PacketLossPanel
            slot={snapshot.history}
            now={nowTimestamp}
            retryPending={snapshot.history.pending}
            onRetry={controller.manualRefresh}
            presentation="standard"
            headingAs="h3"
          />
        }
        poiQuickReference={
          <POIQuickReference
            slot={snapshot.pois}
            retryPending={snapshot.pois.pending}
            onRetry={controller.manualRefresh}
            headingAs="h2"
          />
        }
        latency={
          <NetworkLatencyPanel
            slot={snapshot.history}
            now={nowTimestamp}
            retryPending={snapshot.history.pending}
            onRetry={controller.manualRefresh}
            presentation="compact"
            headingAs="h2"
          />
        }
        throughput={
          <ThroughputPanel
            slot={snapshot.history}
            now={nowTimestamp}
            retryPending={snapshot.history.pending}
            onRetry={controller.manualRefresh}
            presentation="compact"
            headingAs="h2"
          />
        }
      />
    </div>
  );
}
