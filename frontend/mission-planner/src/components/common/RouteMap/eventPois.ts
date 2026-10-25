import type { LatLngExpression } from 'leaflet';
import type { AARSegment, ManualAARTrack } from '@/types/aar';
import type { Waypoint } from '@/services/routes';
import type { Timeline, RouteSample } from '@/services/timeline';
import type { OverviewPoiKind } from '@/services/overview-upcoming-pois';
import type { KaOutage, KuOutageOverride } from '@/types/satellite';

export interface MapEventPoi {
  transport_active?: boolean;
  inactive_reason?: string | null;
  name: string;
  kind: OverviewPoiKind;
  latitude: number;
  longitude: number;
  expected_arrival_time?: string | null;
  description?: string | null;
}

export interface ARSpan {
  id: string;
  label: string;
  coordinates: [number, number][];
}

function coordinate(point: LatLngExpression): [number, number] {
  return Array.isArray(point) ? [point[0], point[1]] : [point.lat, point.lng];
}

function atTime(
  samples: RouteSample[],
  timestamp: number
): [number, number] | null {
  for (let i = 1; i < samples.length; i++) {
    const start = samples[i - 1],
      end = samples[i];
    const from = Date.parse(start.timestamp),
      to = Date.parse(end.timestamp);
    if (timestamp < from || timestamp > to || to <= from) continue;
    const ratio = (timestamp - from) / (to - from);
    const delta = ((end.longitude - start.longitude + 540) % 360) - 180;
    return [
      start.latitude + ratio * (end.latitude - start.latitude),
      ((start.longitude + ratio * delta + 540) % 360) - 180,
    ];
  }
  return null;
}

/** Draft cues before a preview is available; resolved previews are authoritative. */
export function draftEventPois({
  coordinates,
  spans,
  windows,
  waypoints,
  tracks,
  timeline,
  kaOutages,
  kuOutages,
}: {
  coordinates: LatLngExpression[];
  spans: ARSpan[];
  windows: AARSegment[];
  waypoints: Waypoint[];
  tracks: ManualAARTrack[];
  timeline: Timeline | null;
  kaOutages: KaOutage[];
  kuOutages: KuOutageOverride[];
}): MapEventPoi[] {
  const result: MapEventPoi[] = [];
  const add = (
    kind: OverviewPoiKind,
    name: string,
    point: [number, number],
    description?: string
  ) => {
    result.push({
      kind,
      name,
      latitude: point[0],
      longitude: point[1],
      description,
    });
  };
  if (coordinates.length) {
    add('departure', 'Departure', coordinate(coordinates[0]));
    add('arrival', 'Arrival', coordinate(coordinates[coordinates.length - 1]));
  }
  for (const span of spans) {
    if (!span.coordinates.length) continue;
    add('aar_start', 'AR Start', span.coordinates[0], span.label);
    add(
      'aar_end',
      'AR End',
      span.coordinates[span.coordinates.length - 1],
      span.label
    );
  }
  for (const window of windows) {
    if (spans.some((span) => span.id === window.id)) continue;
    // Overrides require resolved preview timing; do not label the old waypoints.
    if (
      window.override_start_elapsed ||
      window.override_start_time ||
      window.override_end_time
    )
      continue;
    for (const [kind, label, waypoint] of [
      ['aar_start', 'AR Start', window.start_waypoint_name],
      ['aar_end', 'AR End', window.end_waypoint_name],
    ] as const) {
      const point = waypoints.find((p) => p.name === waypoint);
      if (point) add(kind, label, [point.latitude, point.longitude], waypoint);
    }
  }
  for (const track of tracks) {
    if (track.points.length < 2) continue;
    const start = track.points[0],
      end = track.points[track.points.length - 1];
    add('aar_start', 'AR Start', [start.latitude, start.longitude], track.name);
    add('aar_end', 'AR End', [end.latitude, end.longitude], track.name);
  }
  for (const [outages, prefix, label] of [
    [kaOutages, 'ka', 'Ka'],
    [kuOutages, 'starshield', 'Starshield'],
  ] as const) {
    const spans: [number, number][] = [];
    for (const outage of [...outages].sort(
      (a, b) => Date.parse(a.start_time) - Date.parse(b.start_time)
    )) {
      const start = Date.parse(outage.start_time),
        end = start + outage.duration_seconds * 1000;
      const previous = spans[spans.length - 1];
      if (previous && start <= previous[1])
        previous[1] = Math.max(previous[1], end);
      else spans.push([start, end]);
    }
    for (const span of spans) {
      for (const [index, boundary, name] of [
        [0, 'start', 'Loss'],
        [1, 'end', 'Restore'],
      ] as const) {
        const point = atTime(timeline?.samples ?? [], span[index]);
        if (point)
          add(`${prefix}_outage_${boundary}`, `${label} ${name}`, point);
      }
    }
  }
  return result;
}
