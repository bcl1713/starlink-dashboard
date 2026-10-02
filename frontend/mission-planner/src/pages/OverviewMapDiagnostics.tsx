import { useStatus } from '@/hooks/api/useStatus';
import { useOverviewHistory } from '@/hooks/api/useOverviewHistory';
import { useSatellites } from '@/hooks/api/useSatellites';
import { useActiveXLink } from '@/hooks/api/useActiveXLink';
import { useCurrentTime } from '@/hooks/useCurrentTime';
import {
  projectGroundEntryPoint,
  projectAircraftPosition,
} from './status-projection';
import { isStatusStale } from './status-freshness';
import { projectAircraftHistory } from './overview-history-projection';
import { overviewHistoryState } from './overview-history-state';
import { projectConfiguredXBandSatellite3d } from './x-band-satellites-projection';
import {
  projectActiveConfiguredXBandSatelliteId,
  projectConfiguredXBandActiveLink,
  calculateConfiguredXBandLookAngles,
} from './x-band-active-link-projection';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';

/** Detailed map configuration/analysis stays available outside Overview. */
export function OverviewMapDiagnostics() {
  const status = useStatus();
  const history = useOverviewHistory();
  const catalog = useSatellites();
  const selection = useActiveXLink();
  const now = useCurrentTime(1000);
  const satellites = projectConfiguredXBandSatellite3d(catalog.data);
  const selectedId = projectActiveConfiguredXBandSatelliteId(selection.data);
  const link = selectedId
    ? projectConfiguredXBandActiveLink(status.data, catalog.data, selectedId)
    : null;
  const angles = link ? calculateConfiguredXBandLookAngles(link) : null;
  const statusText = status.error
    ? status.data
      ? 'Status refresh unavailable · last known'
      : 'Status unavailable'
    : status.isLoading
      ? 'Loading status…'
      : !status.data
        ? 'Status unavailable'
        : isStatusStale(status.data.timestamp, now)
          ? 'Status stale · last known'
          : 'Status sample current';
  const countText = catalog.error
    ? 'Satellite configuration unavailable'
    : catalog.isLoading
      ? 'Loading satellite configuration…'
      : `${satellites.length} configured satellite${satellites.length === 1 ? '' : 's'}`;
  const selectionText = selection.error
    ? 'Satellite selection unavailable'
    : selection.isLoading
      ? 'Loading satellite selection…'
      : selectedId
        ? `Selected planned satellite ${selectedId}`
        : 'No satellite selected';
  const geometryText = angles
    ? `Configured GEO estimate: azimuth ${angles.azimuthDegrees.toFixed(1)}°, elevation ${angles.elevationDegrees.toFixed(1)}°`
    : selectedId
      ? 'Configured GEO geometry unavailable'
      : 'No planned satellite link';
  const points = projectAircraftHistory(
    history.data?.series ?? {},
    ROUTE_OVERLAY_RADIUS
  );
  const rows = [
    ['Status feed', statusText],
    [
      'Aircraft position',
      projectAircraftPosition(status.data ?? {})
        ? 'Current/last-known coordinates'
        : 'Position unavailable',
    ],
    [
      'Track history',
      overviewHistoryState({
        isLoading: history.isLoading,
        isError: history.isError,
        pointCount: points.length,
      }),
    ],
    [
      'Ground entry point',
      projectGroundEntryPoint(status.data ?? {})
        ? 'Current/last-known coordinates'
        : 'GEP unavailable',
    ],
    ['Configured X-band satellites', countText],
    ['Planned satellite', selectionText],
    ['Configured GEO analysis', geometryText],
  ];
  if (selection.data?.state === 'warning')
    rows.push([
      'Configured azimuth rule',
      selection.error
        ? 'Last-known planned link warning'
        : 'Planned link warning',
    ]);
  else if (selectedId && !selection.error && selection.data?.state === 'normal')
    rows.push(['Configured azimuth rule', 'No planned link warning']);
  return (
    <section
      className="mt-6 rounded-lg border p-4"
      aria-label="Overview map diagnostics"
    >
      <h2 className="text-xl font-semibold">Overview map diagnostics</h2>
      <p className="my-2">
        Satellite locations and links are configured planning geometry, not
        measured connectivity. A planned link warning reflects the existing
        configured forbidden-azimuth rule. Retained geometry and coordinates can
        be last known.
      </p>
      <dl className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="font-semibold">{label}</dt>
            <dd className="break-words">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
