import { useState } from 'react';
import type { ImportOperation } from '../../types/itinerary-import';
import type { ItineraryData, ExpectedLeg } from '../../types/planning';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
export function ImportCorrections({
  operation,
  busy,
  onResolve,
}: {
  operation: ImportOperation;
  busy: boolean;
  onResolve: (choices: Record<string, unknown>) => void;
}) {
  const [itinerary, setItinerary] = useState<ItineraryData | undefined>(
    operation.details.itinerary
  );
  const [routes, setRoutes] = useState<Record<string, string>>({});
  const [ars, setArs] = useState<Record<string, string>>({});
  const [ignored, setIgnored] = useState<string[]>([]);
  const routeFiles = operation.details.routes ?? [];
  const update = (id: string, patch: Partial<ExpectedLeg>) =>
    setItinerary((value) =>
      value
        ? {
            ...value,
            expected_legs: (value.expected_legs ?? []).map((l) =>
              l.id === id ? { ...l, ...patch } : l
            ),
          }
        : value
    );
  const routeIssues = operation.issues.filter(
    (i) => i.code === 'route_association_unresolved'
  );
  const sourceIssues = operation.issues.filter(
    (i) =>
      i.code !== 'route_association_unresolved' &&
      i.code !== 'unassigned_route' &&
      i.code !== 'satellite_configuration'
  );
  return (
    <fieldset disabled={busy} className="space-y-4">
      <p>A few inputs need a correction before the mission can be generated.</p>
      {operation.issues.map((issue, i) => (
        <p key={i} role="alert">
          {issue.message}
        </p>
      ))}
      {routeIssues.map((issue) => {
        const leg = itinerary?.expected_legs?.find(
          (l) => l.id === issue.leg_id
        );
        return (
          <label className="block" key={issue.leg_id}>
            Route for leg {leg?.ordinal}: {leg?.departure_airport} →{' '}
            {leg?.arrival_airport}
            <select
              aria-label={`Route for leg ${leg?.ordinal}`}
              className="block w-full rounded border p-2"
              value={routes[issue.leg_id!] ?? ''}
              onChange={(e) =>
                setRoutes({ ...routes, [issue.leg_id!]: e.target.value })
              }
            >
              <option value="">Choose route</option>
              {routeFiles.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.name}
                </option>
              ))}
            </select>
          </label>
        );
      })}
      {operation.issues
        .filter((i) => i.code === 'ar_association_ambiguous')
        .map((issue) => (
          <label className="block" key={issue.field}>
            AR crossing
            <select
              className="block w-full rounded border p-2"
              aria-label="AR crossing"
              value={ars[issue.field!] ?? ''}
              onChange={(e) =>
                setArs({ ...ars, [issue.field!]: e.target.value })
              }
            >
              <option value="">Choose route crossing</option>
              {(operation.details.ar_options?.[issue.field!] ?? []).map(
                (option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                )
              )}
            </select>
          </label>
        ))}
      {routeFiles.length > 1 && (
        <details>
          <summary>Unused route files</summary>
          {routeFiles.map((file) => (
            <label className="block" key={file.id}>
              <input
                type="checkbox"
                checked={ignored.includes(file.id)}
                onChange={(e) =>
                  setIgnored(
                    e.target.checked
                      ? [...ignored, file.id]
                      : ignored.filter((id) => id !== file.id)
                  )
                }
              />{' '}
              Leave out {file.name}
            </label>
          ))}
        </details>
      )}
      {!!sourceIssues.length &&
        itinerary?.expected_legs?.map((leg) => (
          <fieldset className="space-y-2 rounded border p-3" key={leg.id}>
            <legend>Leg {leg.ordinal}</legend>
            <label>
              Departure airport
              <Input
                value={leg.departure_airport}
                onChange={(e) =>
                  update(leg.id, { departure_airport: e.target.value })
                }
              />
            </label>
            <label>
              Arrival airport
              <Input
                value={leg.arrival_airport}
                onChange={(e) =>
                  update(leg.id, { arrival_airport: e.target.value })
                }
              />
            </label>
            <label>
              Departure UTC
              <Input
                value={leg.departure_time}
                onChange={(e) =>
                  update(leg.id, { departure_time: e.target.value })
                }
              />
            </label>
            <label>
              Arrival UTC
              <Input
                value={leg.arrival_time}
                onChange={(e) =>
                  update(leg.id, { arrival_time: e.target.value })
                }
              />
            </label>
            {leg.ar_rows?.map((ar) => (
              <div key={ar.id}>
                <p>{ar.track}</p>
                <label>
                  AR entry UTC
                  <Input
                    value={ar.entry_time}
                    onChange={(e) =>
                      update(leg.id, {
                        ar_rows: (leg.ar_rows ?? []).map((row) =>
                          row.id === ar.id
                            ? { ...row, entry_time: e.target.value }
                            : row
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  AR exit UTC
                  <Input
                    value={ar.exit_time}
                    onChange={(e) =>
                      update(leg.id, {
                        ar_rows: (leg.ar_rows ?? []).map((row) =>
                          row.id === ar.id
                            ? { ...row, exit_time: e.target.value }
                            : row
                        ),
                      })
                    }
                  />
                </label>
              </div>
            ))}
          </fieldset>
        ))}
      {!!itinerary && (
        <Button
          disabled={busy || routeIssues.some((i) => !routes[i.leg_id!])}
          onClick={() =>
            onResolve({
              routes,
              ars,
              ignored_routes: ignored,
              ...(sourceIssues.length ? { itinerary } : {}),
            })
          }
        >
          Continue import
        </Button>
      )}
    </fieldset>
  );
}
