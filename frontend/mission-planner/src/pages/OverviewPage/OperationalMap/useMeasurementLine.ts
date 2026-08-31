import { useEffect, useRef } from 'react';
import L, { type Map as LeafletMap } from 'leaflet';

export function useMeasurementLine(
  map: LeafletMap | null,
  measurePoints: readonly L.LatLng[]
): void {
  const measurementLine = useRef<L.Polyline | null>(null);

  useEffect(() => {
    if (!map) return;
    const line = L.polyline([], {
      color: '#f8fafc',
      dashArray: '4 4',
      pane: 'current-position-layer',
      weight: 2,
    });
    measurementLine.current = line;
    return () => {
      line.removeFrom(map);
      if (measurementLine.current === line) measurementLine.current = null;
    };
  }, [map]);

  useEffect(() => {
    if (!map || !measurementLine.current) return;
    const line = measurementLine.current;
    line.setLatLngs([...measurePoints]);
    if (measurePoints.length > 1 && !map.hasLayer(line)) line.addTo(map);
    if (measurePoints.length <= 1 && map.hasLayer(line)) line.removeFrom(map);
  }, [map, measurePoints]);
}
