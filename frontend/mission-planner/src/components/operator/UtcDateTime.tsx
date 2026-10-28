import { useState } from 'react';
export interface UtcParts {
  date: string;
  time: string;
}
const field =
  'min-h-11 w-full min-w-0 rounded-md border bg-background px-3 py-2';
const fromValue = (value: string | null): UtcParts => ({
  date: value?.slice(0, 10) ?? '',
  time: value?.slice(11, 16) ?? '',
});
/** Explicit Zulu calendar/hour/minute controls, independent of browser locale. */
export function UtcDateTime({
  label,
  value,
  parts,
  onChange,
  onPartsChange,
  disabled = false,
  required = false,
}: {
  label: string;
  value: string | null;
  parts?: UtcParts;
  onChange: (value: string | null) => void;
  onPartsChange?: (parts: UtcParts) => void;
  disabled?: boolean;
  required?: boolean;
}) {
  const [editor, setEditor] = useState(() => ({
    source: value,
    emitted: value,
    parts: fromValue(value),
  }));
  // Only an externally replaced value resets partial controls. Echoes of our own
  // nullable change retain incomplete date/hour/minute input until completed.
  if (editor.source !== value) {
    setEditor({
      source: value,
      emitted: value,
      parts: value === editor.emitted ? editor.parts : fromValue(value),
    });
  }
  const current = parts ?? editor.parts;
  const [hour = '', minute = ''] = current.time.split(':');
  function change(patch: Partial<UtcParts>) {
    const next = { ...current, ...patch };
    onPartsChange?.(next);
    const result =
      next.date && /^\d{2}:\d{2}$/.test(next.time)
        ? `${next.date}T${next.time}:00Z`
        : null;
    const unchanged = result && result.slice(0, 16) === value?.slice(0, 16);
    setEditor({
      source: value,
      emitted: unchanged ? value : result,
      parts: next,
    });
    if (unchanged) return;
    if (result !== value) onChange(result);
  }
  return (
    <fieldset
      disabled={disabled}
      className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-3"
    >
      <legend className="font-medium">{label} · Zulu</legend>
      <label>
        {label} date (Zulu)
        <input
          className={field}
          type="date"
          min="0001-01-01"
          max="9999-12-31"
          required={required || !!hour || !!minute}
          value={current.date}
          onChange={(e) => change({ date: e.target.value })}
        />
      </label>
      <label>
        {label} hour (Zulu)
        <select
          className={field}
          required={required || !!current.date || !!minute}
          value={hour}
          onChange={(e) => change({ time: `${e.target.value}:${minute}` })}
        >
          <option value="">HH</option>
          {Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0')).map(
            (v) => (
              <option key={v} value={v}>
                {v}
              </option>
            )
          )}
        </select>
      </label>
      <label>
        {label} minute (Zulu)
        <select
          className={field}
          required={required || !!current.date || !!hour}
          value={minute}
          onChange={(e) => change({ time: `${hour}:${e.target.value}` })}
        >
          <option value="">MM</option>
          {Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0')).map(
            (v) => (
              <option key={v} value={v}>
                {v}
              </option>
            )
          )}
        </select>
      </label>
    </fieldset>
  );
}
