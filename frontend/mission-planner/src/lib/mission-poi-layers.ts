export const MISSION_POI_LAYERS = [
  { field: 'flight_events_enabled', label: 'Flight Events' },
  { field: 'x_band_events_enabled', label: 'X-Band Events' },
  { field: 'ka_events_enabled', label: 'KA Events' },
  { field: 'starshield_events_enabled', label: 'Starshield Events' },
] as const;

export type MissionPoiLayerField = (typeof MISSION_POI_LAYERS)[number]['field'];
export type MissionPoiVisibility = Partial<
  Record<MissionPoiLayerField, boolean>
>;

export function missionPoiLayer(
  kind: string | null | undefined
): MissionPoiLayerField | null {
  if (kind === 'departure' || kind === 'arrival' || kind?.startsWith('aar_')) {
    return 'flight_events_enabled';
  }
  if (kind?.startsWith('x_band_')) return 'x_band_events_enabled';
  if (kind?.startsWith('ka_')) return 'ka_events_enabled';
  if (kind?.startsWith('starshield_')) return 'starshield_events_enabled';
  return null;
}

export function missionPoiVisible(
  kind: string | null | undefined,
  visibility: MissionPoiVisibility = {}
): boolean {
  const field = missionPoiLayer(kind);
  return field === null || visibility[field] !== false;
}
