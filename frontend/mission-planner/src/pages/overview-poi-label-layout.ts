import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';

export type PoiLabelOffset = readonly [number, number];

const CALLOUTS: readonly PoiLabelOffset[] = [
  [14, -16],
  [-58, -16],
  [14, 16],
  [-58, 16],
  [42, -32],
  [-86, 32],
];

/**
 * Assign stable screen-space callouts so generated POI labels sharing the
 * compact globe remain individually readable while their Html anchors retain
 * normal globe occlusion.
 */
export function overviewPoiLabelOffsets(
  pois: OverviewUpcomingPoi[]
): Record<string, PoiLabelOffset> {
  return Object.fromEntries(
    [...pois]
      .sort((left, right) => left.poi_id.localeCompare(right.poi_id))
      .map((poi, index) => [poi.poi_id, CALLOUTS[index % CALLOUTS.length]])
  );
}
