export interface UtcParts {
  date: string;
  time: string;
}
const field =
  'min-h-11 w-full min-w-0 rounded-md border bg-background px-3 py-2';
/** Calendar controls are explicitly UTC, independent of the browser timezone. */
export function UtcDateTime({
  label,
  value,
  parts,
  onChange,
  onPartsChange,
}: {
  label: string;
  value: string | null;
  parts?: UtcParts;
  onChange: (value: string | null) => void;
  onPartsChange?: (parts: UtcParts) => void;
}) {
  const current = parts ?? {
    date: value?.slice(0, 10) ?? '',
    time: value?.slice(11, 16) ?? '',
  };
  function change(patch: Partial<UtcParts>) {
    const next = { ...current, ...patch };
    onPartsChange?.(next);
    const result =
      next.date && next.time
        ? `${next.date}T${next.time.length === 5 ? `${next.time}:00` : next.time}Z`
        : null;
    if (result?.slice(0, 16) === value?.slice(0, 16)) return;
    if (result !== value) onChange(result);
  }
  return (
    <fieldset className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
      <legend className="font-medium">{label} · UTC</legend>
      <label>
        {label} date (UTC)
        <input
          className={field}
          type="date"
          min="0001-01-01"
          max="9999-12-31"
          required={!!current.time}
          value={current.date}
          onChange={(e) => change({ date: e.target.value })}
        />
      </label>
      <label>
        {label} time (UTC)
        <input
          className={field}
          type="time"
          step="60"
          required={!!current.date}
          value={current.time}
          onChange={(e) => change({ time: e.target.value })}
        />
      </label>
    </fieldset>
  );
}
