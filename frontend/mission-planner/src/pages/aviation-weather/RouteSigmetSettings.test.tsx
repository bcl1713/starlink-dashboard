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
import { advisory } from './fixtures';
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
    name: 'Show intersecting polygons only',
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
    screen.getByRole('switch', { name: 'Show intersecting polygons only' })
  );
  await screen.findByText('Aviation weather settings could not be saved');
  expect(
    screen.getByRole('switch', { name: 'Show intersecting polygons only' })
  ).not.toBeChecked();
  expect(clear()).toBeEnabled();
});
it('lists matching bulletins in route order rather than attention order and labels simulation geometry', async () => {
  const state = setup();
  const { snapshot } = state.fixture;
  const second = {
    ...advisory(),
    id: 'second',
    properties: { ...advisory().properties, series: '2', bulletin_series: '2' },
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
  expect(items).toHaveLength(1);
  expect(items[0]).toHaveTextContent('TEST 1');
  expect(screen.getByText(/Route A.*Simulation route/)).toBeTruthy();
  fireEvent.click(screen.getByText('Cleared'));
  expect(
    screen.getByRole('button', { name: /Show again.*TEST 2/ })
  ).toBeEnabled();
});
it('does not catalogue unrelated, unknown, or future SIGMETs', async () => {
  const state = setup();
  state.setReports([
    state.fixture.data.features[0],
    ...Array.from({ length: 200 }, (_, i) => ({
      ...advisory(),
      id: 'unrelated-' + i,
      properties: { ...advisory().properties, series: 'UNRELATED-' + i },
    })),
  ]);
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  expect(screen.queryByText(/UNRELATED-/)).toBeNull();
  expect(
    screen.queryByRole('region', { name: 'Route intersection unknown' })
  ).toBeNull();
  expect(
    screen.queryByRole('region', { name: 'Future SIGMET reports' })
  ).toBeNull();
  expect(screen.getByText('Pending')).toBeDefined();
  expect(screen.getByText('Cleared').closest('details')).not.toHaveAttribute(
    'open'
  );
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
  fireEvent.click(screen.getByText('Cleared'));
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
    screen.getByRole('switch', { name: 'Show intersecting polygons only' })
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

it('preserves every source variant under one matching notice and one acknowledgement action', async () => {
  const state = setup();
  const first = advisory();
  state.setReports([
    {
      ...first,
      properties: {
        ...first.properties,
        series: 'PROVIDER FIRST',
        raw_text: 'TEST SIGMET\nVALID 061200/061300',
      },
    },
    {
      ...first,
      id: 'source-variant',
      properties: {
        ...first.properties,
        series: 'PROVIDER SECOND',
        raw_text: 'TEST   SIGMET  VALID 061200/061300',
      },
    },
  ]);
  state.setSnapshot({
    ...state.fixture.snapshot,
    entries: [
      {
        ...state.fixture.snapshot.entries[0],
        feature_ids: ['test-advisory', 'source-variant'],
      },
    ],
  });
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory.*TEST 1/ });
  const list = screen.getByRole('list', {
    name: 'Matching route SIGMET bulletins',
  });
  const notices = within(list).getAllByRole('listitem');
  expect(notices).toHaveLength(1);
  expect(notices[0]).toHaveTextContent('PROVIDER FIRST');
  expect(notices[0]).toHaveTextContent('PROVIDER SECOND');
  const reports = within(notices[0]).getAllByRole('article');
  expect(reports).toHaveLength(2);
  expect(
    reports.map((report) => report.querySelector('pre')?.textContent)
  ).toEqual([
    'TEST SIGMET\nVALID 061200/061300',
    'TEST   SIGMET  VALID 061200/061300',
  ]);
  expect(
    screen.getAllByRole('button', { name: /Clear advisory/ })
  ).toHaveLength(1);
  expect(
    screen.queryByRole('region', { name: 'Other current SIGMET reports' })
  ).toBeNull();
  fireEvent.click(
    within(notices[0]).getByRole('button', { name: /Clear advisory/ })
  );
  await screen.findByRole('button', { name: /Show again.*TEST 1/ });
  expect(within(list).getAllByRole('listitem')).toHaveLength(1);
  expect(within(list).getAllByRole('article')).toHaveLength(2);
  expect(screen.getAllByRole('button', { name: /Show again/ })).toHaveLength(1);
});

it('distinguishes provider and canonical series in reports while using the canonical bulletin for actions', async () => {
  const state = setup();
  const first = advisory();
  state.setReports([
    {
      ...first,
      properties: {
        ...first.properties,
        series: 'OSCAR55F',
        bulletin_series: 'OSCAR55',
      },
    },
  ]);
  state.mount();
  const button = await screen.findByRole('button', { name: /Clear advisory/ });
  const list = screen.getByRole('list', {
    name: 'Matching route SIGMET bulletins',
  });
  expect(list).toHaveTextContent(
    'provider series OSCAR55F · canonical series OSCAR55'
  );
  expect(button).toHaveAccessibleName(/TEST OSCAR55/);
  fireEvent.click(button);
  fireEvent.click(screen.getByText('Cleared'));
  await screen.findByRole('button', { name: /Show again/ });
  expect(state.writes).toEqual([
    {
      context_key: hash('c'),
      notice_key: hash('d'),
      semantic_digest: hash('f'),
      acknowledged: true,
    },
  ]);
});
it.each(['no-route', 'unavailable'] as const)(
  'keeps %s feed diagnostics collapsed without listing unrelated reports',
  async (status) => {
    const state = setup();
    state.setSnapshot({
      ...state.fixture.snapshot,
      context: status === 'no-route' ? null : state.fixture.snapshot.context,
      entries: [],
      status,
      complete: false,
    });
    state.mount();
    await screen.findByText('No pending SIGMETs.');
    expect(
      screen.getByText('Diagnostics').closest('details')
    ).not.toHaveAttribute('open');
    expect(
      screen.queryByRole('button', { name: /Clear advisory|Show again/ })
    ).toBeNull();
  }
);
it('acknowledging a selected-only bulletin removes its row entirely', async () => {
  const state = setup();
  const entry = JSON.parse(JSON.stringify(state.fixture.snapshot.entries[0]));
  delete entry.spans;
  entry.selected = true;
  state.setSnapshot({
    ...state.fixture.snapshot,
    entries: [],
    selected_entries: [entry],
  });
  state.mount();
  await screen.findByRole('button', { name: /Clear advisory/ });
  expect(screen.getByText('Selected')).toBeDefined();
  fireEvent.click(clear());
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: /Clear advisory/ })).toBeNull()
  );
  fireEvent.click(screen.getByText('Cleared'));
  expect(screen.queryByRole('button', { name: /Show again/ })).toBeNull();
});
