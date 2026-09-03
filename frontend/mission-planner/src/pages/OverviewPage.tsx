import { useRef } from 'react';
import { OverviewInventory } from './OverviewPage/OverviewInventory';
import type { Cadence } from './OverviewPage/poller';
import { useOverviewData } from './OverviewPage/useOverviewData';
import { useOverviewFullscreen } from './OverviewPage/useOverviewFullscreen';
import './OverviewPage/overview.css';

const cadenceOptions: readonly Cadence[] = [1, 2, 5, 10, 30, 'paused'];

export function OverviewPage() {
  const data = useOverviewData();
  const rootRef = useRef<HTMLElement>(null);
  const fullscreen = useOverviewFullscreen(rootRef);
  return (
    <main
      ref={rootRef}
      className={`overview-page${fullscreen.isFullscreen ? ' overview-page--fullscreen' : ''}`}
      data-testid="overview-root"
      tabIndex={-1}
    >
      <header className="overview-header">
        <div>
          <p className="overview-kicker">Operations</p>
          <h1>Connectivity overview</h1>
        </div>
        <div className="overview-controls">
          <label>
            Refresh cadence
            <select
              value={data.cadence}
              onChange={(event) =>
                data.setCadence(
                  event.target.value === 'paused'
                    ? 'paused'
                    : (Number(event.target.value) as Cadence)
                )
              }
            >
              {cadenceOptions.map((option) => (
                <option value={option} key={option}>
                  {option === 'paused' ? 'Paused' : `${option} second`}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => void data.refreshStatus()}>
            Refresh live status
          </button>
          <button type="button" onClick={() => void data.reconcileHistory()}>
            Reconcile history
          </button>
          <button
            type="button"
            onClick={() =>
              void (fullscreen.isFullscreen
                ? fullscreen.exit()
                : fullscreen.enter())
            }
          >
            {fullscreen.isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          </button>
        </div>
      </header>
      {fullscreen.error && (
        <p className="overview-fullscreen-fallback" role="status">
          {fullscreen.error}
        </p>
      )}
      <OverviewInventory
        status={data.status}
        statusMessage={data.statusMessage}
        latency={data.summaries.latency}
        packetLoss={data.summaries.packetLoss}
        gep={data.gep}
        gepState={data.gepState}
        refreshGep={data.refreshGep}
        pois={data.pois}
        poiState={data.poiState}
        refreshPois={data.refreshPois}
        mapOverlays={data.mapOverlays}
        history={data.history}
        cadence={data.cadence}
        now={data.now}
      />
    </main>
  );
}
