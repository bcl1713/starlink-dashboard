// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GfsStatus } from './GfsStatus';
import { gridFixture, GRID_RUN } from '@/test/gfs-grid';
import { emptyGfsView } from './gfs-controller';
afterEach(cleanup);
it.each(['loading', 'unavailable'] as const)(
  'shows confirmed requested context when %s without fabricating admitted times',
  (state) => {
    const r = render(
      <GfsStatus
        view={{
          ...emptyGfsView,
          state,
          selection: {
            vertical: { kind: 'flight-level', flight_level: 390 },
            horizon_hours: 12,
          },
        }}
      />
    );
    expect(r.container.textContent).toContain('Requested FL390');
    expect(r.container.textContent).toContain('+12 h');
    expect(r.container.textContent).not.toContain('Run ');
    expect(r.container.textContent).not.toContain('Valid ');
  }
);
it.each([0, 6])(
  'distinguishes requested Current from run-relative F%03i and model time kind',
  (lead) => {
    const p = gridFixture().product;
    p.lead_seconds = lead * 3600;
    p.valid_at_ms = GRID_RUN + p.lead_seconds * 1000;
    p.time_kind = lead ? 'forecast' : 'analysis';
    const r = render(
      <GfsStatus
        view={{
          state: 'current',
          now: GRID_RUN,
          selection: {
            vertical: { kind: 'pressure', pressure_pa: 50000 },
            horizon_hours: 0,
          },
          products: { winds: p },
        }}
      />
    );
    expect(r.container.textContent).toContain(
      'Requested 500 hPa · Current horizon'
    );
    expect(r.container.textContent).toContain(
      lead ? 'Numerical-model forecast' : 'Modeled analysis'
    );
    expect(r.container.textContent).toContain(
      `F${String(lead).padStart(3, '0')}`
    );
  }
);
it('shows passive source, UTC run and valid, level and unit legends without Overview selection controls', () => {
  const p = gridFixture().product;
  const r = render(
    <GfsStatus
      view={{
        state: 'stale',
        now: GRID_RUN + 10 * 3600000,
        products: { winds: p, temperature: p },
      }}
    />
  );
  expect(
    screen.getByLabelText('Flight-level atmosphere status').textContent
  ).toContain('NOAA GFS');
  expect(r.container.textContent).toContain('500 hPa');
  expect(r.container.textContent).toContain('Run 2026-10-06 00:00 UTC');
  expect(r.container.textContent).toContain('Valid 2026-10-06 06:00 UTC');
  expect(r.container.textContent).toContain('Stale');
  expect(r.container.textContent).toContain('kt');
  expect(r.container.textContent).toContain('−80');
  expect(r.container.textContent).toContain('clamped');
  expect(screen.queryByRole('combobox')).toBeNull();
  expect(screen.queryByRole('switch')).toBeNull();
  r.rerender(<GfsStatus view={{ ...emptyGfsView, state: 'unavailable' }} />);
  expect(r.container.textContent).toContain('Unavailable');
  expect(r.container.textContent).not.toContain('Valid 2026');
});
it('labels interpolated flight levels explicitly', () => {
  const p = gridFixture().product;
  p.vertical = {
    kind: 'flight-level',
    flight_level: 390,
    reference: 'pressure-altitude-1013.25hpa',
    derivation: 'isa-log-pressure-v1',
    source_pressures_pa: [17500, 20000],
  };
  render(
    <GfsStatus
      view={{ state: 'current', now: GRID_RUN, products: { winds: p } }}
    />
  );
  expect(
    screen.getByLabelText('Flight-level atmosphere status').textContent
  ).toContain('FL390 · ISA / log-pressure interpolation');
});
