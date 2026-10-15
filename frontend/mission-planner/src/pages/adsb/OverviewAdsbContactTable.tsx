import { useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { AdsbContactView } from './overview-adsb-state';
interface Props {
  contacts: readonly AdsbContactView[];
  disabled: boolean;
  onInclude: (hex: string) => void;
  onExclude: (hex: string) => void;
}
export function OverviewAdsbContactTable({
  contacts,
  disabled,
  onInclude,
  onExclude,
}: Props) {
  const [search, setSearch] = useState('');
  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    // Every existing contact field is searchable, including numeric positions
    // and flight data. Derived status is searchable as well.
    return contacts.filter(
      (contact) =>
        !query ||
        JSON.stringify(Object.values(contact))
          .toLocaleLowerCase()
          .includes(query)
    );
  }, [contacts, search]);
  return (
    <section
      aria-label="Active ADS-B aircraft"
      className="min-w-0 border-t pt-5"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Active aircraft</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            All available military and included aircraft. This search does not
            change the Overview filter.
          </p>
        </div>
        <span className="shrink-0 rounded-md bg-muted px-2 py-1 text-xs tabular-nums">
          {filtered.length} / {contacts.length} aircraft
        </span>
      </div>
      <Input
        type="search"
        aria-label="Search aircraft"
        placeholder="Search callsign, registration, type, hex or any aircraft field…"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="mb-3 max-w-xl"
      />
      {filtered.length === 0 ? (
        <p className="py-4 text-sm text-muted-foreground">
          {contacts.length === 0
            ? 'No active aircraft. Saved lists remain available below.'
            : 'No aircraft match this search.'}
        </p>
      ) : (
        <Table
          className="min-w-[1000px] text-xs"
          containerProps={{
            role: 'region',
            'aria-label': 'Aircraft list',
            tabIndex: 0,
            className:
              'max-h-96 rounded-md border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          }}
        >
          <TableCaption className="sr-only">
            Available ADS-B aircraft and current Overview selection
          </TableCaption>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              {[
                'Callsign',
                'Registration',
                'Aircraft type',
                'ICAO hex',
                'Altitude',
                'Ground speed',
                'Position age',
                'Selection',
                'Actions',
              ].map((label) => (
                <TableHead
                  key={label}
                  scope="col"
                  className="sticky top-0 z-10 whitespace-nowrap bg-card text-xs"
                >
                  {label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...filtered]
              .sort((a, b) => a.hex.localeCompare(b.hex))
              .map((c) => (
                <TableRow key={c.hex}>
                  <TableCell className="max-w-40 break-words font-medium [overflow-wrap:anywhere]">
                    {c.callsign?.trim() || '—'}
                  </TableCell>
                  <TableCell className="max-w-32 break-words [overflow-wrap:anywhere]">
                    {c.registration?.trim() || '—'}
                  </TableCell>
                  <TableCell className="max-w-24 break-words [overflow-wrap:anywhere]">
                    {c.aircraft_type?.trim() || '—'}
                  </TableCell>
                  <TableHead
                    scope="row"
                    className="font-mono text-xs text-foreground"
                  >
                    {c.hex}
                  </TableHead>
                  <TableCell
                    className="whitespace-nowrap tabular-nums"
                    title={
                      c.altitude
                        ? `${c.altitude.source === 'barometric' ? 'Barometric' : 'Geometric'} altitude`
                        : undefined
                    }
                  >
                    {c.altitude
                      ? `${c.altitude.value.toLocaleString('en-US')} ft`
                      : '—'}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {c.ground_speed_knots !== null
                      ? `${c.ground_speed_knots.toLocaleString('en-US')} kt`
                      : '—'}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    <span
                      className={
                        c.freshness === 'current'
                          ? 'text-emerald-400'
                          : 'text-amber-400'
                      }
                    >
                      {c.freshness === 'current' ? 'Current' : '◷ Stale'}
                    </span>{' '}
                    · {Math.floor(c.position_age_seconds)}s
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex rounded-md px-2 py-1 text-xs ${c.selection === 'excluded' ? 'bg-destructive/15 text-destructive' : c.included ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'}`}
                    >
                      {c.selection === 'excluded'
                        ? 'Excluded'
                        : c.selection === 'not_selected'
                          ? 'Not selected'
                          : c.included
                            ? 'Included'
                            : 'Background'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1.5">
                      <Button
                        variant={c.included ? 'default' : 'outline'}
                        size="sm"
                        type="button"
                        disabled={disabled}
                        aria-pressed={c.included}
                        aria-label={`Include ${c.hex}`}
                        onClick={() => onInclude(c.hex)}
                      >
                        Include
                      </Button>
                      <Button
                        variant={
                          c.selection === 'excluded' ? 'destructive' : 'outline'
                        }
                        size="sm"
                        type="button"
                        disabled={disabled}
                        aria-pressed={c.selection === 'excluded'}
                        aria-label={`Exclude ${c.hex}`}
                        onClick={() => onExclude(c.hex)}
                      >
                        Exclude
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
