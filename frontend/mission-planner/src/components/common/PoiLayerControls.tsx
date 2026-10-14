import {
  MISSION_POI_LAYERS,
  type MissionPoiVisibility,
  type MissionPoiLayerField,
} from '@/lib/mission-poi-layers';

export function PoiLayerControls({
  value,
  onChange,
}: {
  value: MissionPoiVisibility;
  onChange: (field: MissionPoiLayerField, enabled: boolean) => void;
}) {
  return (
    <fieldset className="flex flex-wrap gap-x-5 gap-y-2 rounded-lg border border-border px-3 py-2 text-sm">
      <legend className="px-1 font-medium">POI layers</legend>
      {MISSION_POI_LAYERS.map(({ field, label }) => (
        <label key={field} className="flex min-h-8 items-center gap-2">
          <input
            type="checkbox"
            checked={value[field] !== false}
            onChange={(event) => onChange(field, event.target.checked)}
          />
          {label}
        </label>
      ))}
    </fieldset>
  );
}
