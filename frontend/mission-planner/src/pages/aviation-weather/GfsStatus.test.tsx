// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GfsStatus } from './GfsStatus';
import { gridFixture, GRID_RUN } from '@/test/gfs-grid';
import { emptyGfsView } from './gfs-controller';
afterEach(cleanup);
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
