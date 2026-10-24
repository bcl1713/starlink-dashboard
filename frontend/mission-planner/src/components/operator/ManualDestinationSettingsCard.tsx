import { useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  manualDestinationApi,
  type ManualDestination,
} from '@/services/manual-destination';
import { ConfigurationSection } from '@/pages/ConfigurationSection';

const settingsKey = ['overview', 'manual-destination'];

export function ManualDestinationSettingsCard() {
  const { data, isError } = useQuery({
    queryKey: settingsKey,
    queryFn: manualDestinationApi.get,
  });
  return (
    <ConfigurationSection
      title="Manual destination"
      description="Set a shared Overview destination when no mission leg is active. Arrival is estimated from direct distance and fresh groundspeed. An active mission takes precedence; this destination stays saved."
    >
      {data ? (
        <DestinationForm initial={data.destination} />
      ) : isError ? (
        <p role="alert">
          Destination settings unavailable. Reload to try again.
        </p>
      ) : (
        <p role="status">Loading destination settings…</p>
      )}
    </ConfigurationSection>
  );
}

function DestinationForm({ initial }: { initial: ManualDestination | null }) {
  const id = useId();
  const client = useQueryClient();
  const [query, setQuery] = useState('');
  const [name, setName] = useState(initial?.name ?? '');
  const [latitude, setLatitude] = useState(
    initial ? String(initial.latitude) : ''
  );
  const [longitude, setLongitude] = useState(
    initial ? String(initial.longitude) : ''
  );
  const [airportCode, setAirportCode] = useState(initial?.airport_code ?? null);
  const [validation, setValidation] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const lookup = useMutation({ mutationFn: manualDestinationApi.search });
  const save = useMutation({
    mutationFn: manualDestinationApi.save,
    onSuccess: (settings) => {
      client.setQueryData(settingsKey, settings);
      void client.invalidateQueries({ queryKey: ['overview-upcoming-pois'] });
      setMessage(
        settings.destination ? 'Destination saved' : 'Destination cleared'
      );
      if (!settings.destination) {
        setName('');
        setLatitude('');
        setLongitude('');
        setAirportCode(null);
      }
    },
  });
  const saveDestination = () => {
    setMessage(null);
    const lat = Number(latitude),
      lon = Number(longitude);
    if (
      !name.trim() ||
      name.trim().length > 120 ||
      !latitude.trim() ||
      !longitude.trim() ||
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      Math.abs(lat) > 90 ||
      Math.abs(lon) > 180
    ) {
      setValidation(
        'Enter a destination name (up to 120 characters) and valid coordinates: latitude −90 to 90, longitude −180 to 180.'
      );
      return;
    }
    setValidation(null);
    save.mutate({
      name: name.trim(),
      latitude: lat,
      longitude: lon,
      airport_code: airportCode,
    });
  };
  return (
    <div className="space-y-4">
      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          lookup.mutate(query.trim());
        }}
      >
        <label className="block text-sm font-medium" htmlFor={`${id}-airport`}>
          Airport search
        </label>
        <div className="flex flex-wrap gap-2">
          <Input
            className="min-w-40 flex-1"
            id={`${id}-airport`}
            value={query}
            maxLength={120}
            placeholder="ICAO, IATA or airport name"
            onChange={(e) => {
              setQuery(e.target.value);
              lookup.reset();
            }}
          />
          <Button
            type="submit"
            variant="outline"
            disabled={query.trim().length < 2 || lookup.isPending}
          >
            Search airports
          </Button>
        </div>
        {lookup.isPending && <p role="status">Searching airports…</p>}
        {lookup.isError && (
          <p role="alert">
            Airport search unavailable. Try again or enter destination
            coordinates below.
          </p>
        )}
        {lookup.isSuccess && lookup.data.length === 0 && (
          <p role="status">
            No airports found. Try another code or name, or enter coordinates
            below.
          </p>
        )}
        {lookup.data && (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {lookup.data.map((airport) => (
              <li key={airport.ident}>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-auto w-full justify-start whitespace-normal text-left"
                  onClick={() => {
                    setName(airport.name);
                    setLatitude(String(airport.latitude));
                    setLongitude(String(airport.longitude));
                    setAirportCode(
                      airport.icao_code || airport.iata_code || airport.ident
                    );
                    setValidation(null);
                    setMessage(null);
                    lookup.reset();
                  }}
                >
                  {airport.name} · {airport.ident}
                  {airport.iata_code ? ` / ${airport.iata_code}` : ''} ·{' '}
                  {airport.municipality || airport.country}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted-foreground">
          Offline airport catalog from{' '}
          <a href="https://ourairports.com/data/" className="underline">
            OurAirports
          </a>
          . Select a result to fill the destination, or enter a name and
          coordinates.
        </p>
      </form>
      <form
        className="space-y-3"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          saveDestination();
        }}
      >
        <div>
          <label
            className="mb-1 block text-sm font-medium"
            htmlFor={`${id}-name`}
          >
            Destination name
          </label>
          <Input
            id={`${id}-name`}
            value={name}
            maxLength={120}
            onChange={(e) => {
              setName(e.target.value);
              setAirportCode(null);
              setMessage(null);
            }}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label
              className="mb-1 block text-sm font-medium"
              htmlFor={`${id}-latitude`}
            >
              Latitude
            </label>
            <Input
              id={`${id}-latitude`}
              type="number"
              step="any"
              min={-90}
              max={90}
              value={latitude}
              onChange={(e) => {
                setLatitude(e.target.value);
                setAirportCode(null);
                setMessage(null);
              }}
            />
          </div>
          <div>
            <label
              className="mb-1 block text-sm font-medium"
              htmlFor={`${id}-longitude`}
            >
              Longitude
            </label>
            <Input
              id={`${id}-longitude`}
              type="number"
              step="any"
              min={-180}
              max={180}
              value={longitude}
              onChange={(e) => {
                setLongitude(e.target.value);
                setAirportCode(null);
                setMessage(null);
              }}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={save.isPending}>
            Save destination
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={save.isPending}
            onClick={() => {
              setValidation(null);
              setMessage(null);
              save.mutate(null);
            }}
          >
            Clear destination
          </Button>
        </div>
        {validation && <p role="alert">{validation}</p>}
        {save.isPending && <p role="status">Saving destination…</p>}
        {save.isError && (
          <p role="alert">
            Unable to save destination. Your draft is preserved. Please try
            again.
          </p>
        )}
        {message && <p role="status">{message}</p>}
      </form>
    </div>
  );
}
