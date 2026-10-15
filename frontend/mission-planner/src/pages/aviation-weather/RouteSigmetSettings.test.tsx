// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, it, vi } from 'vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AviationSettingsCard } from './AviationSettingsCard';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import { advisory, NOW } from './fixtures';
import { weatherDigest } from '@/services/aviation-grid';
import {
  parseRouteSigmetSnapshot,
  type RouteSigmetSnapshot,
} from '@/services/route-sigmets';
import { optionalWeatherBudget } from './weather-budget';
const settings = {
  metar: false,
  taf: false,
  sigmet: true,
  sigmet_intersecting_only: false,
  winds: false,
  temperature: false,
  revision: 1,
  gfs_selection: {
    vertical: { kind: 'pressure' as const, pressure_pa: 50000 as const },
    horizon_hours: 0 as const,
  },
};
const clients: QueryClient[] = [];
afterEach(async () => {
  cleanup();
  for (const client of clients.splice(0)) {
    await client.cancelQueries();
    client.clear();
  }
  await new Promise((resolve) => setTimeout(resolve, 0));
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  expect(optionalWeatherBudget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    gpu: 0,
    slots: 0,
    waiting: 0,
  });
});
function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
function setup(initial = settings) {
  const raw = routeSnapshot();
  const snapshot = parseRouteSigmetSnapshot(raw.snapshot);
  if (!snapshot.context) throw new Error('Expected fixture route context');
  const fixture = {
    ...raw,
    snapshot: { ...snapshot, context: snapshot.context },
  };
  let current: RouteSigmetSnapshot = fixture.snapshot;
  let payloadStatus = 200;
  let reports: unknown[] = fixture.data.features;
  let write: (change: Record<string, unknown>) => Promise<Response> = async (
    change
  ) => {
    current = {
      ...current,
      state_revision: current.state_revision + 1,
      entries: current.entries.map((e) => ({
        ...e,
        acknowledged: change.acknowledged as boolean,
      })),
    };
    return json({
      ...change,
      state_revision: current.state_revision,
      attention_order: 1,
    });
  };
  const getSettings = vi
    .spyOn(aviationWeatherApi, 'getSettings')
    .mockResolvedValue(initial);
  const save = vi.spyOn(aviationWeatherApi, 'updateSettings');
  const writes: unknown[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: RequestInfo | URL, init?: RequestInit) => {
      if (String(path).endsWith('acknowledgement')) {
        const change = JSON.parse(String(init?.body));
        writes.push(change);
        return write(change);
      }
      const data = { ...fixture.data, features: reports };
      const bytes = new TextEncoder().encode(JSON.stringify(data));
      current.sigmet_product.payload = {
        ...fixture.snapshot.sigmet_product.payload!,
        sha256: weatherDigest(bytes),
        encoded_bytes: bytes.length,
        decoded_bytes: bytes.length * 4,
      };
      return String(path).endsWith('.json')
        ? new Response(bytes, {
            status: payloadStatus,
            headers: { 'Content-Type': 'application/geo+json' },
          })
        : json(current);
    })
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  return {
    client,
    getSettings,
    save,
    writes,
    setWrite: (next: typeof write) => {
      write = next;
    },
    setSnapshot: (next: typeof current) => {
      current = next;
    },
    setPayloadStatus: (status: number) => {
      payloadStatus = status;
    },
    setReports: (next: unknown[]) => {
      reports = next;
    },
    fixture,
    mount: () =>
      render(
        <QueryClientProvider client={client}>
          <AviationSettingsCard />
        </QueryClientProvider>
      ),
  };
}
const clear = () =>
  screen.getByRole('button', { name: /Clear advisory.*TEST 1/ });
it('remembers the filter while SIGMET is off and changes it only after a confirmed save', async () => {
  const state = setup({
    ...settings,
    sigmet: false,
    sigmet_intersecting_only: true,
  });
  state.mount();
  const filter = await screen.findByRole('switch', {
    name: 'Intersecting route only',
  });
  await waitFor(() => expect(filter).toBeChecked());
  expect(filter).toBeDisabled();
  const pending = deferred<typeof settings>();
  state.save.mockReturnValue(pending.promise);
  fireEvent.click(
    screen.getByRole('switch', { name: 'International SIGMET advisories' })
  );
  await screen.findByText('Saving aviation weather settings…');
  expect(filter).toBeDisabled();
  expect(filter).toBeChecked();
  state.setSnapshot({ ...state.fixture.snapshot, settings_revision: 2 });
  await act(async () =>
    pending.resolve({
      ...settings,
      sigmet_intersecting_only: true,
      revision: 2,
    })
  );
  await waitFor(() => expect(filter).toBeEnabled());
  await screen.findByRole('button', { name: /Clear advisory/ });
  const filterSave = deferred<typeof settings>();
  state.save.mockReturnValue(filterSave.promise);
  fireEvent.click(filter);
  await screen.findByText('Saving aviation weather settings…');
  expect(filter).toBeChecked();
  expect(screen.queryByRole('button', { name: /Show again/ })).toBeNull();
  expect(state.save).toHaveBeenLastCalledWith({
    sigmet_intersecting_only: false,
  });
  state.setSnapshot({ ...state.fixture.snapshot, settings_revision: 3 });
  await act(async () => filterSave.resolve({ ...settings, revision: 3 }));
  await waitFor(() => expect(filter).not.toBeChecked());
  await waitFor(() => expect(clear()).toBeEnabled());
  expect(state.writes).toEqual([]);
});
it('keeps the confirmed filter and pending notice after a failed settings write', async () => {
  const state = setup();
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  state.save.mockRejectedValue(new Error('save failed'));
  fireEvent.click(
    screen.getByRole('switch', { name: 'Intersecting route only' })
  );
  await screen.findByText('Aviation weather settings could not be saved');
  expect(
    screen.getByRole('switch', { name: 'Intersecting route only' })
  ).not.toBeChecked();
  expect(clear()).toBeEnabled();
});
it('lists matching bulletins in route order rather than attention order and labels simulation geometry', async () => {
  const state = setup();
  const { snapshot } = state.fixture;
  const second = {
    ...advisory(),
    id: 'second',
    properties: { ...advisory().properties, series: '2' },
  };
  state.setReports([advisory(), second]);
  state.setSnapshot({
    ...snapshot,
    context: {
      ...snapshot.context,
      source: 'simulation',
      runtime_id: 'runtime',
      run_id: 'run',
    },
    entries: [
      {
        ...snapshot.entries[0],
        attention_order: 999,
        spans: [{ ...snapshot.entries[0].spans[0], segment_index: 4 }],
      },
      {
        ...snapshot.entries[0],
        notice_key: hash('1'),
        bulletin_key: hash('2'),
        feature_ids: ['second'],
        attention_order: 1,
        acknowledged: true,
        spans: [{ ...snapshot.entries[0].spans[0], segment_index: 0 }],
      },
    ],
  });
  state.mount();
  const list = await screen.findByRole('list', {
    name: 'Matching route SIGMET bulletins',
  });
  const items = within(list).getAllByRole('listitem');
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent('TEST 2');
  expect(items[0]).toHaveTextContent('Acknowledged');
  expect(items[1]).toHaveTextContent('Pending');
  expect(screen.getByText(/Route A.*Simulation route/)).toBeTruthy();
  expect(
    screen.getByRole('button', { name: /Show again.*TEST 2/ })
  ).toBeEnabled();
});
it('separates unknown and future reports and preserves original UTC, source, bounds and bulletin details', async () => {
  const state = setup();
  const a = advisory();
  state.setReports([
    {
      ...a,
      properties: {
        ...a.properties,
        bulletin_series: 'PROVIDER 7',
        issued_at_ms: NOW - 1000,
        revision: '2',
        amends: 'previous',
        vertical: {
          lower: 180,
          upper: 340,
          unit: 'flight-level',
          reference: 'FL',
        },
      },
    },
    {
      ...a,
      id: 'unknown',
      geometry: null,
      properties: { ...a.properties, series: 'U', raw_text: 'UNLOCATED RAW' },
    },
    {
      ...a,
      id: 'future',
      properties: {
        ...a.properties,
        series: 'F',
        valid_from_ms: NOW + 100000,
        raw_text: 'FUTURE RAW',
      },
    },
  ]);
  state.setSnapshot({
    ...state.fixture.snapshot,
    complete: false,
    status: 'incomplete',
    reason: 'Some boundaries unknown',
    unresolved: [{ feature_id: 'unknown', reason: 'unlocated' }],
    future_feature_ids: ['future'],
  });
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  const unknown = screen.getByRole('region', {
    name: 'Route intersection unknown',
  });
  const future = screen.getByRole('region', { name: 'Future SIGMET reports' });
  expect(unknown).toHaveTextContent('UNLOCATED RAW');
  expect(unknown).toHaveTextContent('unlocated');
  expect(future).toHaveTextContent('FUTURE RAW');
  expect(within(unknown).queryByRole('button')).toBeNull();
  expect(within(future).queryByRole('button')).toBeNull();
  const list = screen.getByRole('list', {
    name: 'Matching route SIGMET bulletins',
  });
  expect(list).toHaveTextContent('PROVIDER 7');
  expect(list).toHaveTextContent('2026-10-06T11:59:59.000 UTC');
  expect(list).toHaveTextContent('180 flight-level');
  expect(list).toHaveTextContent('340 flight-level FL');
  expect(list).toHaveTextContent('TEST SIGMET');
  expect(list).toHaveTextContent('amends previous');
  expect(
    screen.getByText(/Source AWC.*retrieved.*2026-10-06T12:00:00.000 UTC/)
  ).toBeTruthy();
  expect(
    screen.getByText(/Altitude and passage-time match not evaluated/)
  ).toBeTruthy();
  expect(screen.getByText(/Missing reports mean unknown weather/)).toBeTruthy();
});
it('waits for confirmed Clear and Show again writes with the exact notice identity', async () => {
  const state = setup();
  const pending = deferred<Response>();
  state.setWrite(() => pending.promise);
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  fireEvent.click(clear());
  await screen.findByText(/Saving advisory state/);
  expect(clear()).toBeDisabled();
  expect(screen.queryByRole('button', { name: /Show again/ })).toBeNull();
  expect(state.writes).toEqual([
    {
      context_key: hash('c'),
      notice_key: hash('d'),
      semantic_digest: hash('f'),
      acknowledged: true,
    },
  ]);
  await act(async () =>
    pending.resolve(
      json({
        ...(state.writes[0] as object),
        state_revision: 2,
        attention_order: 1,
      })
    )
  );
  const show = await screen.findByRole('button', {
    name: /Show again.*TEST 1/,
  });
  expect(show).toBeEnabled();
  state.setWrite(async (change) =>
    json({ ...change, state_revision: 3, attention_order: 2 })
  );
  fireEvent.click(show);
  await waitFor(() => expect(clear()).toBeEnabled());
  expect(state.writes[1]).toEqual({
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: false,
  });
});
it('failed_clear_keeps_notice_pending with an enabled retry and truthful error', async () => {
  const state = setup();
  state.setWrite(async () => json({ detail: 'failed' }, 503));
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  fireEvent.click(clear());
  await screen.findByRole('alert', { name: '' });
  expect(screen.getByRole('alert')).toHaveTextContent(/Could not save.*TEST 1/);
  expect(clear()).toBeEnabled();
  expect(screen.queryByRole('button', { name: /Show again/ })).toBeNull();
});
it('refreshes stale identity after conflict without claiming the replacement was cleared', async () => {
  const state = setup();
  state.setWrite(async () => {
    state.setSnapshot({
      ...state.fixture.snapshot,
      generation_id: hash('8'),
      context: {
        ...state.fixture.snapshot.context,
        context_key: hash('7'),
        route_name: 'Replacement route',
      },
    });
    return json({ detail: 'changed' }, 409);
  });
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  fireEvent.click(clear());
  await screen.findByText(/Replacement route/);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    /changed.*refresh/i
  );
  expect(clear()).toBeEnabled();
  expect(screen.queryByText(/Advisory state saved/)).toBeNull();
});
it('retains other current reports for review without creating notice actions or showing cancelled and expired reports', async () => {
  const state = setup();
  const a = advisory();
  state.setReports([
    a,
    {
      ...a,
      id: 'other',
      properties: { ...a.properties, series: 'O', raw_text: 'OTHER RAW' },
    },
    {
      ...a,
      id: 'cancelled',
      properties: {
        ...a.properties,
        cancelled: true,
        raw_text: 'CANCELLED RAW',
      },
    },
    {
      ...a,
      id: 'expired',
      properties: {
        ...a.properties,
        valid_from_ms: NOW - 10000,
        valid_to_ms: NOW,
        expires_at_ms: NOW,
        raw_text: 'EXPIRED RAW',
      },
    },
  ]);
  state.mount();
  const other = await screen.findByRole('region', {
    name: 'Other current SIGMET reports',
  });
  expect(other).toHaveTextContent('OTHER RAW');
  expect(within(other).queryByRole('button')).toBeNull();
  expect(screen.queryByText('CANCELLED RAW')).toBeNull();
  expect(screen.queryByText('EXPIRED RAW')).toBeNull();
});

it('keeps unavailable original reports explicit and disables notice actions instead of substituting report data', async () => {
  const state = setup();
  state.setPayloadStatus(503);
  state.mount();
  const button = await screen.findByRole('button', {
    name: /Clear advisory.*report unavailable/,
  });
  expect(button).toBeDisabled();
  expect(screen.getByText(/Original report unavailable/)).toBeTruthy();
  expect(
    screen.getByText(/Reports unavailable or refresh failed/)
  ).toBeTruthy();
  expect(screen.queryByText('TEST SIGMET')).toBeNull();
  expect(state.writes).toEqual([]);
});
it('shows route unavailable in intersecting mode without claiming clear weather', async () => {
  const state = setup({ ...settings, sigmet_intersecting_only: true });
  state.setSnapshot({
    ...state.fixture.snapshot,
    context: null,
    entries: [],
    status: 'no-route',
    complete: false,
    reason: 'No active route',
  });
  state.mount();
  await screen.findByText(/No usable route/);
  expect(screen.getByText('Route unavailable')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /Clear advisory/ })).toBeNull();
  expect(screen.getByText(/Missing reports mean unknown weather/)).toBeTruthy();
});

it('loads reports without GPU drawings and releases report demand when SIGMET is confirmed off', async () => {
  const state = setup();
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  expect(optionalWeatherBudget.snapshot().decoded).toBeGreaterThan(0);
  expect(optionalWeatherBudget.snapshot().gpu).toBe(0);
  state.save.mockResolvedValue({ ...settings, sigmet: false, revision: 2 });
  fireEvent.click(
    screen.getByRole('switch', { name: 'International SIGMET advisories' })
  );
  await waitFor(() =>
    expect(
      screen.getByRole('switch', { name: 'International SIGMET advisories' })
    ).not.toBeChecked()
  );
  expect(
    screen.getByRole('switch', { name: 'Intersecting route only' })
  ).toBeDisabled();
  expect(screen.queryByRole('button', { name: /Clear advisory/ })).toBeNull();
  await waitFor(() =>
    expect(optionalWeatherBudget.snapshot()).toMatchObject({
      encoded: 0,
      decoded: 0,
      gpu: 0,
      slots: 0,
    })
  );
});
