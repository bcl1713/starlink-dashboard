import type {
  PlanningSatelliteOptions,
  SatelliteSelection,
} from '../../types/planning';
export function PermittedSatellites({
  options,
  value,
  onChange,
}: {
  options: PlanningSatelliteOptions;
  value: SatelliteSelection;
  onChange: (value: SatelliteSelection) => void;
}) {
  const ids = value.permitted_satellite_ids ?? [];
  const access = value.access_confirmation;
  const confirmed =
    !!access?.confirmed &&
    access.satellite_ids.length === ids.length &&
    ids.every((id) => access.satellite_ids.includes(id));
  return (
    <fieldset className="min-w-0 space-y-3 rounded-xl border p-4">
      <legend className="font-semibold">Permitted X-band satellites</legend>
      <p className="text-sm text-muted-foreground">
        Select satellites for which you have service access. Catalog display
        visibility does not change these plan settings.
      </p>
      {options.satellites
        .filter((s) => s.transport === 'X')
        .map((s) => (
          <div key={s.id}>
            <label className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                checked={ids.includes(s.id)}
                disabled={!s.eligible}
                onChange={(e) =>
                  onChange({
                    ...value,
                    permitted_satellite_ids: e.target.checked
                      ? [...ids, s.id]
                      : ids.filter((id) => id !== s.id),
                    access_confirmation: null,
                  })
                }
              />
              {s.label}
            </label>
            {!s.eligible && (
              <p className="text-sm text-destructive">
                {s.error?.message ?? 'No valid configured X-band position'}
              </p>
            )}
          </div>
        ))}
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={confirmed}
          disabled={!ids.length}
          onChange={(e) =>
            onChange({
              ...value,
              access_confirmation: {
                satellite_ids: [...ids],
                confirmed: e.target.checked,
                confirmed_at: e.target.checked
                  ? new Date().toISOString()
                  : null,
              },
            })
          }
        />
        I confirm service access to the selected satellites
      </label>
      {!confirmed && (
        <p role="alert" className="text-sm text-destructive">
          {ids.length
            ? 'Confirm service access before optimization or reviewed save.'
            : 'Select permitted X-band satellites before optimization or reviewed save.'}{' '}
          You can still save a draft.
        </p>
      )}
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={value.starshield_enabled ?? true}
          onChange={(e) =>
            onChange({ ...value, starshield_enabled: e.target.checked })
          }
        />
        Starshield enabled for this plan
      </label>
    </fieldset>
  );
}
