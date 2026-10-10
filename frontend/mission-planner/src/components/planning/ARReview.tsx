import type {
  ARMatchCandidates,
  ExpectedLeg,
  ItineraryAR,
  RouteAnchor,
} from '../../types/planning';
import type { RoutePoint } from '../../services/routes';
import { arRouteSpan } from '../../services/planning';
import { createClientId } from '../../lib/clientId';
import { RouteMap } from '../common/RouteMap';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export function ARReview({
  leg,
  rows,
  onChange,
  sectionStatus,
  onSectionStatusChange,
  noARsConfirmed,
  onNoARsConfirmedChange,
  candidates = [],
  coordinates = [],
  routePoints = [],
}: {
  leg: ExpectedLeg;
  rows: ItineraryAR[];
  onChange: (rows: ItineraryAR[]) => void;
  sectionStatus: NonNullable<ExpectedLeg['ar_section_status']>;
  onSectionStatusChange: (
    value: NonNullable<ExpectedLeg['ar_section_status']>
  ) => void;
  noARsConfirmed: boolean;
  onNoARsConfirmedChange: (value: boolean) => void;
  candidates?: ARMatchCandidates[];
  coordinates?: [number, number][];
  routePoints?: RoutePoint[];
}) {
  const update = (id: string, patch: Partial<ItineraryAR>) => {
    onNoARsConfirmedChange(false);
    onChange(
      rows.map((row) =>
        row.id === id ? { ...row, confirmed: false, ...patch } : row
      )
    );
  };
  const anchorLabel = (anchor: RouteAnchor) =>
    `${anchor.fraction === 0 ? 'Exact' : 'Interpolated'} · ${anchor.source_time} · ${anchor.latitude.toFixed(5)}, ${anchor.longitude.toFixed(5)} · occurrence ${anchor.occurrence_id}`;
  const manualAnchors: RouteAnchor[] = leg.route
    ? routePoints.flatMap((point, index) => {
        if (
          !point.occurrence_id ||
          !point.expected_arrival_time ||
          !Number.isFinite(Date.parse(point.expected_arrival_time)) ||
          !Number.isFinite(point.latitude) ||
          !Number.isFinite(point.longitude)
        )
          return [];
        return [
          {
            route_id: leg.route!.route_id,
            content_hash: leg.route!.content_hash,
            segment_index: index,
            fraction: 0,
            occurrence_id: point.occurrence_id,
            source_time: point.expected_arrival_time,
            latitude: point.latitude,
            longitude: point.longitude,
            timing_mode: 'route_bound' as const,
          },
        ];
      })
    : [];
  const spans = rows
    .filter((row) => row.match_status !== 'excluded')
    .map((row) => ({
      id: row.id,
      label: row.track,
      coordinates: arRouteSpan(
        coordinates,
        row.start_anchor,
        row.end_anchor,
        leg.route ?? undefined
      ),
    }))
    .filter((span) => span.coordinates.length > 1);
  return (
    <section aria-label="AR windows" className="min-w-0 space-y-4">
      <h2 className="font-semibold">AR windows</h2>
      <p className="text-sm text-muted-foreground">
        Review source UTC times and altitude units. Select occurrence anchors
        rather than waypoint names. Imported AR windows use sector exclusions;
        Manual AR Tracks remain independent overlays.
      </p>
      <label className="block">
        AR section correction
        <select
          aria-label="AR section correction"
          className="block min-h-11 w-full rounded border bg-background p-2"
          value={sectionStatus}
          onChange={(e) => {
            onSectionStatusChange(
              e.target.value as NonNullable<ExpectedLeg['ar_section_status']>
            );
            onNoARsConfirmedChange(false);
          }}
        >
          <option value="unrecognized">Unrecognized — needs correction</option>
          <option value="listed">AR rows listed (correct below)</option>
          <option value="empty">Checked source — no listed ARs</option>
        </select>
      </label>
      {sectionStatus === 'unrecognized' && (
        <p role="alert" className="text-destructive">
          Unrecognized AR section. Check the source and explicitly correct the
          section before review.
        </p>
      )}
      {!rows.some((row) => row.match_status !== 'excluded') && (
        <label className="flex min-h-11 items-center gap-2">
          <input
            type="checkbox"
            disabled={sectionStatus === 'unrecognized'}
            checked={noARsConfirmed}
            onChange={(e) => onNoARsConfirmedChange(e.target.checked)}
          />
          I confirm no AR windows for this leg
        </label>
      )}
      {rows.map((row) => {
        const original =
          leg.ar_rows?.find((source) => source.id === row.id) ?? row;
        const excluded = row.match_status === 'excluded';
        const validTime =
          /(?:Z|[+-]\d{2}:\d{2})$/.test(row.entry_time) &&
          /(?:Z|[+-]\d{2}:\d{2})$/.test(row.exit_time) &&
          Date.parse(row.entry_time) < Date.parse(row.exit_time) &&
          Date.parse(row.entry_time) >= Date.parse(leg.departure_time) &&
          Date.parse(row.exit_time) <= Date.parse(leg.arrival_time);
        const validAltitude =
          row.source_altitude != null &&
          Number.isFinite(row.source_altitude) &&
          row.source_altitude > 0 &&
          !!row.confirmed_units;
        const start = row.start_anchor;
        const end = row.end_anchor;
        const matchesSourceTime = (time: string, source: string) => {
          const actual = Date.parse(time);
          const expected = Date.parse(source);
          return row.source_time_precision === 'minute'
            ? Math.floor(actual / 60_000) === Math.floor(expected / 60_000)
            : actual === expected;
        };
        const orderedAnchors =
          !!start &&
          !!end &&
          Date.parse(start.source_time) < Date.parse(end.source_time) &&
          matchesSourceTime(start.source_time, row.entry_time) &&
          matchesSourceTime(end.source_time, row.exit_time) &&
          start.segment_index + start.fraction <
            end.segment_index + end.fraction &&
          start.route_id === leg.route?.route_id &&
          end.route_id === leg.route.route_id &&
          start.content_hash === leg.route.content_hash &&
          end.content_hash === leg.route.content_hash;
        const match = candidates.find(
          (candidate) => candidate.ar_id === row.id
        );
        const correctedTime =
          row.entry_time !== original.entry_time ||
          row.exit_time !== original.exit_time;
        const anchorOptions = (
          key: 'start_anchor' | 'end_anchor',
          proposed: RouteAnchor[] = []
        ) => {
          const available =
            proposed.length && !correctedTime
              ? proposed
              : [...proposed, ...manualAnchors];
          const saved = row[key];
          if (
            saved &&
            !available.some(
              (anchor) => JSON.stringify(anchor) === JSON.stringify(saved)
            )
          )
            return [...available, saved];
          return available;
        };
        const entryOptions = anchorOptions(
          'start_anchor',
          match?.start_candidates
        );
        const exitOptions = anchorOptions('end_anchor', match?.end_candidates);
        const chooseAnchor = (
          key: 'start_anchor' | 'end_anchor',
          options: RouteAnchor[]
        ) => (
          <label className="block">
            {key === 'start_anchor' ? 'Entry' : 'Exit'} occurrence {row.track}
            <select
              aria-label={`${key === 'start_anchor' ? 'Entry' : 'Exit'} occurrence ${row.track}`}
              className="block min-h-11 w-full rounded border bg-background p-2"
              value={options.findIndex(
                (anchor) => JSON.stringify(anchor) === JSON.stringify(row[key])
              )}
              onChange={(e) => {
                const anchor = options[Number(e.target.value)] ?? null;
                const next = { ...row, [key]: anchor };
                update(row.id, {
                  [key]: anchor,
                  match_status:
                    next.start_anchor && next.end_anchor
                      ? 'matched'
                      : 'unresolved',
                });
              }}
            >
              <option value={-1}>Choose a route occurrence</option>
              {options.map((anchor, index) => (
                <option key={`${anchor.occurrence_id}-${index}`} value={index}>
                  {anchorLabel(anchor)}
                </option>
              ))}
            </select>
          </label>
        );
        return (
          <fieldset
            key={row.id}
            className="min-w-0 space-y-3 rounded-xl border p-4"
          >
            <legend className="font-semibold">
              {row.track || 'New AR row'}
            </legend>
            {((row.start_anchor &&
              row.start_anchor.route_id !== leg.route?.route_id) ||
              (row.end_anchor &&
                row.end_anchor.route_id !== leg.route?.route_id)) && (
              <p role="alert">
                Retained anchors from the previous route. Choose current timed
                occurrences for {row.track}; prior corrections remain visible
                until resolved.
              </p>
            )}
            <p className="break-words text-sm">
              Page {original.source_page ?? 'manual'}, row{' '}
              {original.source_row ?? 'manual'} ·{' '}
              {row.match_status ?? 'unresolved'}
            </p>
            <p className="break-words text-sm">
              Source UTC: {original.entry_time} → {original.exit_time} (
              {original.source_time_precision} precision)
            </p>
            <p className="break-words text-sm text-muted-foreground">
              {original.source_text}
            </p>
            <div className="grid min-w-0 gap-3 sm:grid-cols-2">
              <label>
                Track {row.track}
                <Input
                  aria-label={`Track ${row.track}`}
                  value={row.track}
                  onChange={(e) => update(row.id, { track: e.target.value })}
                />
              </label>
              <label>
                Altitude {row.track}
                <Input
                  aria-label={`Altitude ${row.track}`}
                  type="number"
                  value={row.source_altitude ?? ''}
                  onChange={(e) =>
                    update(row.id, {
                      source_altitude:
                        e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Entry UTC {row.track}
                <Input
                  aria-label={`Entry UTC ${row.track}`}
                  value={row.entry_time}
                  aria-invalid={!validTime}
                  onChange={(e) =>
                    update(row.id, {
                      entry_time: e.target.value,
                      start_anchor: null,
                      end_anchor: null,
                      match_status: 'unresolved',
                    })
                  }
                />
              </label>
              <label>
                Exit UTC {row.track}
                <Input
                  aria-label={`Exit UTC ${row.track}`}
                  value={row.exit_time}
                  aria-invalid={!validTime}
                  onChange={(e) =>
                    update(row.id, {
                      exit_time: e.target.value,
                      start_anchor: null,
                      end_anchor: null,
                      match_status: 'unresolved',
                    })
                  }
                />
              </label>
              <label>
                Altitude units {row.track}
                <select
                  aria-label={`Altitude units ${row.track}`}
                  aria-invalid={!validAltitude}
                  className="block min-h-11 w-full rounded border bg-background p-2"
                  value={row.confirmed_units ?? ''}
                  onChange={(e) =>
                    update(row.id, {
                      confirmed_units: (e.target.value ||
                        null) as ItineraryAR['confirmed_units'],
                    })
                  }
                >
                  <option value="">Confirm units</option>
                  <option value="flight_level">
                    Flight level (pressure altitude)
                  </option>
                  <option value="feet">Feet</option>
                  <option value="meters">Meters</option>
                </select>
              </label>
            </div>
            {!excluded && !validAltitude && (
              <p role="alert" className="text-sm text-destructive">
                Confirm altitude and units before confirming this AR window.
              </p>
            )}
            {row.confirmed_units === 'flight_level' && (
              <p className="text-sm text-muted-foreground">
                Flight levels are pressure altitude. Geometric conversion uses
                approximately 30.48 meters per flight level.
              </p>
            )}
            {!validTime && (
              <p role="alert" className="text-sm text-destructive">
                Use increasing timezone-aware UTC times within this leg.
              </p>
            )}
            {!excluded &&
              (entryOptions.length > 0 || exitOptions.length > 0) && (
                <div className="space-y-3">
                  {chooseAnchor('start_anchor', entryOptions)}
                  {chooseAnchor('end_anchor', exitOptions)}
                </div>
              )}
            {start && (
              <p className="break-words text-sm">
                Matched entry: {anchorLabel(start)}
              </p>
            )}
            {end && (
              <p className="break-words text-sm">
                Matched exit: {anchorLabel(end)}
              </p>
            )}
            {!excluded && !orderedAnchors && (
              <p role="alert" className="text-sm text-destructive">
                Unresolved route span. Upload a matching route or choose ordered
                occurrences within this AR window before confirmation.
              </p>
            )}
            <label className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                aria-label={`Exclude ${row.track}`}
                checked={excluded}
                onChange={(e) =>
                  update(row.id, {
                    match_status: e.target.checked ? 'excluded' : 'unresolved',
                  })
                }
              />
              Exclude {row.track}
            </label>
            {excluded && (
              <>
                <label>
                  Exclusion note {row.track}
                  <Input
                    aria-label={`Exclusion note ${row.track}`}
                    value={row.exclusion_note ?? ''}
                    aria-invalid={!row.exclusion_note?.trim()}
                    onChange={(e) =>
                      update(row.id, { exclusion_note: e.target.value })
                    }
                  />
                </label>
                {!row.exclusion_note?.trim() && (
                  <p role="alert" className="text-sm text-destructive">
                    Exclusion note required.
                  </p>
                )}
              </>
            )}
            <label className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                aria-label={`Confirm ${row.track}`}
                checked={row.confirmed ?? false}
                disabled={
                  sectionStatus === 'unrecognized' ||
                  !validTime ||
                  (excluded
                    ? !row.exclusion_note?.trim()
                    : !validAltitude || !orderedAnchors)
                }
                onChange={(e) =>
                  update(row.id, { confirmed: e.target.checked })
                }
              />
              Confirm {row.track}
            </label>
          </fieldset>
        );
      })}
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          onNoARsConfirmedChange(false);
          onSectionStatusChange('listed');
          onChange([
            ...rows,
            {
              id: createClientId(),
              track: 'New AR',
              entry_time: leg.departure_time,
              exit_time: leg.arrival_time,
              source_time_precision: 'second',
              match_status: 'unresolved',
              confirmed: false,
            },
          ]);
        }}
      >
        Add AR row
      </Button>
      {leg.route && (
        <RouteMap
          coordinates={coordinates}
          anchoredARSpans={spans}
          height="clamp(20rem, 50vw, 32rem)"
        />
      )}
    </section>
  );
}
