import { Button } from '@/components/ui/button';
import { useState } from 'react';
import { useTransportAvailability } from '@/hooks/api/useTransportAvailability';
import {
  legAvailability,
  rfTransports,
  type AvailabilityOverrides,
  type RFTransport,
} from '@/services/transportAvailability';
type Selection = 'inherit' | 'available' | 'unavailable';
export function TransportAvailabilityControls({
  missionId,
  legId,
}: {
  missionId: string;
  legId?: string;
}) {
  const availability = useTransportAvailability(missionId);
  const [edits, setEdits] = useState<Partial<Record<RFTransport, Selection>>>(
    {}
  );
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const view = availability.data;
  const row = legId ? legAvailability(view, legId) : undefined;
  const effective =
    row &&
    ('planning_effective' in row ? row.planning_effective : row.effective);
  const saved = legId
    ? (row?.overrides ?? view?.leg_overrides[legId] ?? {})
    : (view?.defaults ?? {});
  return (
    <section
      aria-label={
        legId ? 'Leg transport availability' : 'Mission transport availability'
      }
      className="min-w-0 space-y-3 rounded-xl border border-border p-4"
    >
      <h2 className="text-lg font-semibold">Transport availability</h2>
      <p className="text-sm text-muted-foreground">
        {legId
          ? 'Inherit mission defaults or set this leg independently.'
          : 'Mission defaults apply to new legs and legs that inherit. Deliberate leg settings are retained.'}{' '}
        Saving regenerates affected profiles.
      </p>
      {!view ? (
        <p role={availability.isError ? 'alert' : 'status'}>
          {availability.isError
            ? 'Availability could not be loaded.'
            : 'Loading availability…'}
        </p>
      ) : (
        <form
          className="space-y-3"
          onSubmit={async (e) => {
            e.preventDefault();
            setMessage('');
            setError('');
            const updates: AvailabilityOverrides = legId ? { ...saved } : {};
            for (const { key } of rfTransports) {
              if (!(key in edits)) continue;
              if (edits[key] === 'inherit') delete updates[key];
              else updates[key] = edits[key] === 'available';
            }
            try {
              await availability.savePlanned(
                legId
                  ? { leg_overrides: { [legId]: updates } }
                  : { defaults: updates }
              );
              setEdits({});
              setMessage('Availability saved. Profiles regenerated.');
            } catch {
              setError(
                'Availability was not confirmed. Your edits are retained. Refresh to review the confirmed state or retry saving.'
              );
            }
          }}
        >
          <div className="grid min-w-0 gap-3 sm:grid-cols-3">
            {rfTransports.map(({ key, label }) => (
              <label
                key={key}
                className="min-w-0 space-y-1 text-sm font-medium"
              >
                <span>{label}</span>
                <select
                  className="block min-h-11 w-full min-w-0 rounded border bg-background p-2"
                  aria-label={label}
                  value={
                    edits[key] ??
                    (legId && saved[key] === undefined
                      ? 'inherit'
                      : saved[key] === false
                        ? 'unavailable'
                        : 'available')
                  }
                  disabled={
                    availability.isSaving ||
                    availability.isError ||
                    (!!legId && !row)
                  }
                  onChange={(e) => {
                    setEdits((draft) => ({
                      ...draft,
                      [key]: e.target.value as Selection,
                    }));
                    setMessage('');
                  }}
                >
                  {legId && (
                    <option value="inherit">
                      Inherit mission
                      {view.defaults[key] !== undefined
                        ? ` (${view.defaults[key] ? 'available' : 'unavailable'})`
                        : ''}
                    </option>
                  )}
                  <option value="available">Available</option>
                  <option value="unavailable">Unavailable</option>
                </select>
                {row && (
                  <span className="block text-xs text-muted-foreground">
                    Planned: {row.planned[key] ? 'available' : 'unavailable'}
                    {effective &&
                      ` · Effective: ${effective[key] ? 'available' : 'unavailable'}`}
                  </span>
                )}
              </label>
            ))}
          </div>
          <Button
            type="submit"
            className="h-auto min-h-11 whitespace-normal"
            disabled={
              availability.isSaving ||
              availability.isError ||
              !Object.keys(edits).length
            }
          >
            {availability.isSaving
              ? 'Saving availability…'
              : 'Save availability'}
          </Button>
        </form>
      )}
      {(availability.isError || error) && (
        <>
          <p role="alert">
            {error ||
              'Availability could not be refreshed. Last confirmed settings are shown.'}
          </p>
          <Button
            variant="outline"
            className="min-h-11"
            onClick={() => void availability.refetch()}
          >
            Refresh availability
          </Button>
        </>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
