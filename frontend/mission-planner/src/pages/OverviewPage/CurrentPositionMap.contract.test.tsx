import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('leaflet', () => ({
  divIcon: (options: object) => options,
}));

vi.mock('react-leaflet', () => ({
  MapContainer: ({
    children,
    className,
  }: React.PropsWithChildren<{ className?: string }>) => (
    <div className={className} data-map-container="true">
      {children}
    </div>
  ),
  TileLayer: ({ url }: { url: string }) => (
    <div data-tile-layer="true" data-url={url} />
  ),
  Polyline: ({ color }: { color: string }) => (
    <div data-polyline="true" data-color={color} />
  ),
  Marker: ({ children }: React.PropsWithChildren) => (
    <div data-marker="true">{children}</div>
  ),
  Tooltip: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
  ZoomControl: () => <div data-zoom-control="true" />,
  ScaleControl: () => <div data-scale-control="true" />,
  useMap: () => ({
    getContainer: () => document.createElement('div'),
    invalidateSize: () => undefined,
  }),
  useMapEvents: () => null,
}));

import { CurrentPositionMap } from './CurrentPositionMap';

describe('CurrentPositionMap Grafana-card contract', () => {
  it('renders the configured tile layers, operational overlays, and controls', () => {
    const html = renderToStaticMarkup(
      <CurrentPositionMap
        latitude={10}
        longitude={179}
        heading={135}
        route={{ west: [[10, -179]], east: [[10, 179]] }}
        activeLinks={{
          normal: { west: [[10, -179]], east: [[15, 179]] },
          warning: { west: [], east: [[10, 170]] },
        }}
        history={{ west: [[9, -179]], east: [[10, 179]] }}
        markers={{
          flightRoute: [
            { id: 'route', name: 'Waypoint', latitude: 10, longitude: 179 },
          ],
          satellites: [
            { id: 'sat', name: 'SAT-1', latitude: 11, longitude: 178 },
          ],
          missionEvents: [
            { id: 'event', name: 'Event', latitude: 12, longitude: 177 },
          ],
        }}
        groundEntryPoint={{ display: 'GEP', latitude: 13, longitude: 176 }}
      />
    );

    expect(html).toContain(
      'server.arcgisonline.com/ArcGIS/rest/services/World_Imagery'
    );
    expect(html).not.toContain('Weather Radar');
    expect(html).not.toContain('rainviewer');
    expect(html).toContain('data-zoom-control="true"');
    expect(html).toContain('data-scale-control="true"');
    expect(html).toContain('Planned Route');
    expect(html).toContain('Active X-band Link');
    expect(html).toContain('Active X-band Link status: Warning');
    expect(html).toContain('data-color="#facc15"');
    expect(html).not.toContain('Active X-band Link - Normal');
    expect(html).not.toContain('Active X-band Link - Warning');
    expect(html).not.toContain('Measure distance');
    expect(html).toContain('Position History');
    expect(html).toContain('Waypoint');
    expect(html).toContain('SAT-1');
    expect(html).toContain('Event');
    expect(html).toContain('GEP');
    expect(html).toContain('Heading 135°');
    expect(html).not.toContain('Measure distance');
    expect(html).not.toContain('<svg');
  });

  it('keeps core map identity without weather controls or loading state', () => {
    const html = renderToStaticMarkup(
      <CurrentPositionMap
        latitude={10}
        longitude={20}
        heading={0}
        route={{ west: [], east: [] }}
        activeLinks={{
          normal: { west: [], east: [] },
          warning: { west: [], east: [] },
        }}
        history={{ west: [], east: [] }}
        markers={{ flightRoute: [], satellites: [], missionEvents: [] }}
        groundEntryPoint={null}
      />
    );

    expect(html).not.toContain('Radar unavailable');
    expect(html).not.toContain('Retry radar');
    expect(html).toContain('server.arcgisonline.com/ArcGIS/rest/services');
    expect(html).toContain('Active X-band Link status: Normal');
    expect(html).toContain('data-color="#22c55e"');
  });
});
