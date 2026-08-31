import { useId, useState } from 'react';
import type { OverviewClockPreference } from './preferences';

interface ClockRowProps {
  readonly clock: OverviewClockPreference;
  readonly index: number;
  readonly total: number;
  readonly onRelabelClock: (id: string, label: string) => void;
  readonly onMoveClock: (id: string, direction: 'up' | 'down') => void;
  readonly onRemoveClock: (id: string) => void;
}

export function ClockRow({
  clock,
  index,
  total,
  onRelabelClock,
  onMoveClock,
  onRemoveClock,
}: ClockRowProps) {
  const relabelId = useId();
  const [draft, setDraft] = useState(clock.label);
  const [isEditing, setEditing] = useState(false);
  const isUtc = clock.id === 'utc';
  const visibleDraft = isEditing ? draft : clock.label;
  const trimmed = visibleDraft.trim();
  const canRelabel = trimmed.length >= 1 && trimmed.length <= 64;

  return (
    <div className="grid min-w-0 gap-2 rounded-md border p-3 sm:grid-cols-[1fr_auto]">
      <div className="min-w-0 space-y-2">
        <label className="text-sm font-medium" htmlFor={relabelId}>
          {`Relabel ${clock.label}`}
        </label>
        {isUtc ? (
          <p className="text-sm text-muted-foreground">UTC first.</p>
        ) : (
          <input
            id={relabelId}
            className="min-h-11 w-full min-w-0 rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={visibleDraft}
            onFocus={() => {
              setDraft(clock.label);
              setEditing(true);
            }}
            onChange={(event) => {
              setDraft(event.target.value);
              setEditing(true);
            }}
            onBlur={() => {
              if (canRelabel && trimmed !== clock.label) {
                onRelabelClock(clock.id, trimmed);
              }
              setEditing(false);
            }}
          />
        )}
      </div>
      {!isUtc ? (
        <div className="flex min-w-0 items-end gap-2">
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            aria-label={`Move ${clock.label} up`}
            disabled={index <= 1}
            onClick={() => onMoveClock(clock.id, 'up')}
          >
            Up
          </button>
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            aria-label={`Move ${clock.label} down`}
            disabled={index >= total - 1}
            onClick={() => onMoveClock(clock.id, 'down')}
          >
            Down
          </button>
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Remove ${clock.label}`}
            onClick={() => onRemoveClock(clock.id)}
          >
            Remove
          </button>
        </div>
      ) : null}
    </div>
  );
}
