import { useState } from 'react';
import type { ImportOperation } from '../../types/itinerary-import';
import { Button } from '../ui/button';
function changeLabel(field: string) {
  const part = field.split('.').at(-1) ?? '';
  return (
    (
      {
        adjusted_departure_time: 'Takeoff time',
        route_id: 'Route',
        initial_x_satellite_id: 'Starting X-band satellite',
        x_transitions: 'Satellite handovers',
        aar_windows: 'AR windows',
        notes: 'Notes',
        starshield_enabled: 'Starshield',
        ka_outages: 'Ka outages',
        ku_overrides: 'Ku outages',
        name: 'Leg name',
      } as Record<string, string>
    )[part] ?? 'Leg configuration'
  );
}
export function RevisionPreview({
  operation,
  busy,
  onApply,
}: {
  operation: ImportOperation;
  busy: boolean;
  onApply: (choices: Record<string, string>) => void;
}) {
  const [choices, setChoices] = useState<Record<string, string>>({});
  const revision = operation.details.revision;
  const conflicts = revision?.conflicts ?? [];
  return (
    <div className="space-y-4">
      <p>
        Review the updated itinerary before applying it. Your current mission
        stays in place until you apply this revision.
      </p>
      {!!revision?.changes.length && (
        <ul>
          {(
            revision.change_details ??
            revision.changes.map((field) => ({
              field,
              leg: revision.leg_names?.[field.split('.')[1]] ?? 'Leg',
              current: undefined,
              incoming: undefined,
            }))
          ).map((change) => (
            <li key={change.field} className="mb-3">
              <strong>
                {change.leg}: {changeLabel(change.field)}
              </strong>
              <div>
                Current:{' '}
                <pre className="whitespace-pre-wrap break-words">
                  {JSON.stringify(change.current ?? 'Not present', null, 2)}
                </pre>
              </div>
              <div>
                Updated:{' '}
                <pre className="whitespace-pre-wrap break-words">
                  {JSON.stringify(change.incoming ?? 'Removed', null, 2)}
                </pre>
              </div>
            </li>
          ))}
        </ul>
      )}
      {!revision?.changes.length && !conflicts.length && (
        <p>No changes to the current leg configuration.</p>
      )}
      {conflicts.map((conflict) => (
        <label className="block" key={conflict.field}>
          {revision?.leg_names?.[conflict.field.split('.')[1]] ?? 'Leg'}:{' '}
          {changeLabel(conflict.field)}
          <div>
            Current:{' '}
            <pre className="whitespace-pre-wrap break-words">
              {JSON.stringify(conflict.current, null, 2)}
            </pre>
          </div>
          <div>
            Updated:{' '}
            <pre className="whitespace-pre-wrap break-words">
              {JSON.stringify(conflict.incoming, null, 2)}
            </pre>
          </div>
          <select
            className="block w-full rounded border p-2"
            aria-label={`Resolve ${changeLabel(conflict.field)}`}
            value={choices[conflict.field] ?? ''}
            onChange={(e) =>
              setChoices({ ...choices, [conflict.field]: e.target.value })
            }
          >
            <option value="">Choose which to keep</option>
            <option value="retain">Keep my existing edit</option>
            <option value="replace">Use the updated itinerary</option>
          </select>
        </label>
      ))}
      <Button
        disabled={busy || conflicts.some((c) => !choices[c.field])}
        onClick={() => onApply(choices)}
      >
        Apply revision
      </Button>
    </div>
  );
}
