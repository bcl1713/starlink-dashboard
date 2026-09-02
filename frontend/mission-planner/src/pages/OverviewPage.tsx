import { OverviewInventory } from './OverviewPage/OverviewInventory';
import type { Cadence } from './OverviewPage/poller';
import { useOverviewData } from './OverviewPage/useOverviewData';
import './OverviewPage/overview.css';

const cadenceOptions: readonly Cadence[] = [1, 2, 5, 10, 30, 'paused'];

export function OverviewPage() {
  const data = useOverviewData();
  return (
    <main className="overview-page">
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
        </div>
      </header>
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
        cadence={data.cadence}
        now={data.now}
      />
    </main>
  );
}
