import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ItineraryIntake, ItinerarySourceLeg } from './ItineraryIntake';
import { planningMissionController } from '../../services/planning-mutations';
import { PermittedSatellites } from './PermittedSatellites';
import {
  planningApi,
  planningErrorMessage,
  defaultSatelliteSelection,
} from '../../services/planning';
import { createClientId } from '../../lib/clientId';
import type {
  ExpectedLeg,
  ItineraryData,
  ItineraryPreview,
  SatelliteSelection,
  BatchRoutePreview,
  PlanningView,
} from '../../types/planning';

export function CreateFromItinerary({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (missionId: string) => void;
}) {
  const returnFocus = useRef<HTMLElement | null>(null);
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent
        className="max-h-[90dvh] overflow-y-auto sm:max-w-3xl"
        onOpenAutoFocus={() => {
          returnFocus.current =
            document.activeElement instanceof HTMLElement
              ? document.activeElement
              : null;
        }}
        onCloseAutoFocus={(e) => {
          if (returnFocus.current?.isConnected) {
            e.preventDefault();
            returnFocus.current.focus({ preventScroll: true });
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Create from itinerary</DialogTitle>
          <DialogDescription>
            Upload a text-bearing itinerary PDF, correct extracted UTC values,
            and attach the KML batch before reviewing route occurrences. Your
            mission draft is retained while you complete source review.
          </DialogDescription>
        </DialogHeader>
        {open && <ItineraryForm onClose={onClose} onSuccess={onSuccess} />}
      </DialogContent>
    </Dialog>
  );
}
function ItineraryForm({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (id: string) => void;
}) {
  const client = useQueryClient();
  const options = useQuery({
    queryKey: ['planning-satellite-options'],
    queryFn: planningApi.satelliteOptions,
    retry: false,
  });
  const [selection, setSelection] = useState<SatelliteSelection | null>(null);
  const selected =
    selection ?? defaultSatelliteSelection(options.data ?? { satellites: [] });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ItineraryPreview | null>(null);
  const [itinerary, setItinerary] = useState<ItineraryData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [routeFiles, setRouteFiles] = useState<File[]>([]);
  const [created, setCreated] = useState<PlanningView | null>(null);
  const [routeBatch, setRouteBatch] = useState<BatchRoutePreview | null>(null);
  const [importUnits, setImportUnits] = useState<
    'flight_level' | 'feet' | 'meters'
  >('flight_level');
  const defaultRows = useRef(new Set<string>());
  const idempotency = useRef(createClientId());
  const extract = async () => {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const result = await planningApi.previewItinerary(file);
      setPreview(result);
      const parsed = result.parsed_values ?? { name: '', expected_legs: [] };
      defaultRows.current = new Set(
        (parsed.expected_legs ?? []).flatMap((leg) =>
          (leg.ar_rows ?? [])
            .filter((row) => row.unit_origin === 'import_default')
            .map((row) => row.id)
        )
      );
      setItinerary({
        ...parsed,
        expected_legs: (parsed.expected_legs ?? []).map((leg) => ({
          ...leg,
          ar_rows: (leg.ar_rows ?? []).map((row) =>
            defaultRows.current.has(row.id)
              ? {
                  ...row,
                  confirmed_units: importUnits,
                  unit_origin:
                    importUnits === 'flight_level'
                      ? 'import_default'
                      : 'operator_override',
                }
              : row
          ),
        })),
      });
      idempotency.current = createClientId();
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const updateLeg = (id: string, updates: Partial<ExpectedLeg>) =>
    setItinerary((value) =>
      value
        ? {
            ...value,
            expected_legs: value.expected_legs?.map((leg) =>
              leg.id === id ? { ...leg, ...updates } : leg
            ),
          }
        : value
    );
  const confirm = async () => {
    if (!itinerary || !preview) return;
    const utc = (time: string) =>
      /(?:Z|[+-]\d{2}:\d{2})$/.test(time) && Number.isFinite(Date.parse(time));
    if (!itinerary.name.trim() || !itinerary.expected_legs?.length) {
      setError('Enter a mission name and at least one expected leg.');
      return;
    }
    for (const leg of itinerary.expected_legs) {
      if (
        !leg.departure_airport.trim() ||
        !leg.arrival_airport.trim() ||
        !utc(leg.departure_time) ||
        !utc(leg.arrival_time) ||
        Date.parse(leg.departure_time) >= Date.parse(leg.arrival_time)
      ) {
        setError(
          `Correct airports and increasing UTC times for leg ${leg.ordinal}.`
        );
        return;
      }
      for (const row of leg.ar_rows ?? [])
        if (
          !utc(row.entry_time) ||
          !utc(row.exit_time) ||
          Date.parse(row.entry_time) >= Date.parse(row.exit_time) ||
          Date.parse(row.entry_time) < Date.parse(leg.departure_time) ||
          Date.parse(row.exit_time) > Date.parse(leg.arrival_time) ||
          (row.match_status === 'excluded' && !row.exclusion_note?.trim())
        ) {
          setError(
            `Correct UTC times or exclusion note for ${row.track} in leg ${leg.ordinal}.`
          );
          return;
        }
    }
    setBusy(true);
    setError('');
    try {
      const view = await planningApi.create({
        preview_id: preview.preview_id,
        itinerary: {
          ...itinerary,
          expected_legs: (itinerary.expected_legs ?? []).map((leg) => ({
            ...leg,
            draft: { no_ars_confirmed: false },
          })),
        },
        idempotency_key: idempotency.current,
        ...selected,
      });
      client.setQueryData(['planning', view.mission.id], view);
      client.invalidateQueries({ queryKey: ['missions'] });
      if (routeFiles.length) {
        try {
          const staged = await planningMissionController(
            client,
            view.mission.id
          ).enqueueMutation(
            (current) =>
              planningApi.previewRoutes(
                view.mission.id,
                routeFiles,
                current.revision
              ),
            () => null
          );
          setRouteBatch(staged);
        } catch (failure) {
          setError(planningErrorMessage(failure));
        }
      }
      setCreated(view);
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  if (created)
    return (
      <div className="space-y-3">
        {error && <p role="alert">{error}</p>}
        <ItineraryIntake
          view={created}
          initialFiles={routeFiles}
          initialPreview={routeBatch}
          onChange={setCreated}
          onContinue={() => {
            onSuccess(created.mission.id);
            onClose();
          }}
        />
      </div>
    );
  return (
    <fieldset disabled={busy} className="min-w-0 space-y-4">
      <label className="block">
        Itinerary PDF
        <Input
          type="file"
          accept=".pdf,application/pdf"
          aria-label="Itinerary PDF"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <label className="block">
        Initial route KMLs
        <Input
          aria-label="Initial route KMLs"
          type="file"
          multiple
          accept=".kml"
          onChange={(event) =>
            setRouteFiles(Array.from(event.target.files ?? []))
          }
        />
      </label>
      <p className="text-sm text-muted-foreground">
        Maximum 10 MiB. Rotated text pages are supported; scan-only PDFs require
        a text-bearing source.
      </p>
      <Button onClick={extract} disabled={busy || !file}>
        {busy ? 'Working…' : 'Extract itinerary'}
      </Button>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {preview?.field_errors?.map((issue, index) => (
        <p
          role="alert"
          className="break-words text-sm text-destructive"
          key={index}
        >
          Extraction: {issue.message}{' '}
          {issue.source_page
            ? `(page ${issue.source_page}, row ${issue.source_row ?? '?'})`
            : ''}
          . Correct the fields below; unresolved inputs require review.
        </p>
      ))}
      {preview?.source_evidence?.length ? (
        <details>
          <summary>Extracted source evidence</summary>
          {preview.source_evidence.map((e, i) => (
            <p className="break-words text-sm" key={i}>
              Page {e.source_page}, row {e.source_row}: {e.source_text}
            </p>
          ))}
        </details>
      ) : null}
      {itinerary && (
        <>
          <label className="block">
            Mission name
            <Input
              aria-label="Mission name"
              value={itinerary.name}
              onChange={(e) =>
                setItinerary({ ...itinerary, name: e.target.value })
              }
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            {(['itinerary_revision', 'aircraft', 'call_sign'] as const).map(
              (key) => (
                <label key={key}>
                  {key.replaceAll('_', ' ')}
                  <Input
                    aria-label={key.replaceAll('_', ' ')}
                    type={key === 'itinerary_revision' ? 'number' : 'text'}
                    value={itinerary[key] ?? ''}
                    onChange={(e) =>
                      setItinerary({
                        ...itinerary,
                        [key]:
                          key === 'itinerary_revision'
                            ? e.target.value
                              ? Number(e.target.value)
                              : null
                            : e.target.value,
                      })
                    }
                  />
                </label>
              )
            )}
          </div>
          <p>
            Attach routes before reviewing AR occurrences. Extracted source
            values remain editable here; missing route matches are pending
            dependencies.
          </p>
          <details>
            <summary>Advanced import altitude units</summary>
            <label>
              Unlabeled AR altitude units
              <select
                aria-label="Unlabeled AR altitude units"
                value={importUnits}
                onChange={(event) => {
                  const units = event.target.value as typeof importUnits;
                  setImportUnits(units);
                  setItinerary({
                    ...itinerary,
                    expected_legs: (itinerary.expected_legs ?? []).map(
                      (leg) => ({
                        ...leg,
                        ar_rows: (leg.ar_rows ?? []).map((row) =>
                          defaultRows.current.has(row.id)
                            ? {
                                ...row,
                                confirmed_units: units,
                                unit_origin: 'operator_override',
                                confirmed: false,
                              }
                            : row
                        ),
                      })
                    ),
                  });
                }}
              >
                <option value="flight_level">Flight level (default)</option>
                <option value="feet">Feet</option>
                <option value="meters">Meters</option>
              </select>
            </label>
            <p>
              Changes apply only to new unlabeled rows. Explicit source units
              are preserved.
            </p>
          </details>
          {itinerary.expected_legs?.map((leg) => (
            <ItinerarySourceLeg
              key={leg.id}
              leg={leg}
              onChange={(updates) => updateLeg(leg.id, updates)}
            />
          ))}
          <Button
            variant="outline"
            onClick={() =>
              setItinerary({
                ...itinerary,
                expected_legs: [
                  ...(itinerary.expected_legs ?? []),
                  {
                    id: createClientId(),
                    ordinal: (itinerary.expected_legs?.length ?? 0) + 1,
                    departure_airport: '',
                    arrival_airport: '',
                    departure_time: '',
                    arrival_time: '',
                    ar_rows: [],
                    ar_section_status: 'unrecognized',
                  },
                ],
              })
            }
          >
            Add expected leg
          </Button>
          {options.data && (
            <PermittedSatellites
              options={options.data}
              value={selected}
              onChange={setSelection}
            />
          )}
          {options.error && (
            <p role="alert">
              Unable to load configured satellites. You can create a draft and
              configure access during leg review.
            </p>
          )}
          <p className="text-sm text-muted-foreground">
            Creation defaults copy into every leg. Later edits apply to the
            selected leg. Review AR windows and satellite access, generate and
            compare a proposal, then save the reviewed plan.
          </p>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button
              onClick={confirm}
              disabled={busy}
              className="h-auto min-h-11 max-w-full whitespace-normal"
            >
              Continue to route attachments
            </Button>
          </div>
        </>
      )}
    </fieldset>
  );
}
