// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GfsStatus } from './GfsStatus';
import { gridFixture, GRID_RUN } from '@/test/gfs-grid';
import { emptyGfsView, type GfsProducts } from './gfs-controller';
afterEach(cleanup);

it.each(['off', 'loading', 'unavailable'] as const)(
  'does not imply rendered weather when %s without admitted products',
  (state) => {
    render(<GfsStatus view={{ ...emptyGfsView, state }} />);
    expect(screen.queryByLabelText('Atmosphere legend')).toBeNull();
  }
);

it.each([0, 6])(
  'shows the selected horizon +%i without run metadata',
  (horizon) => {
    const p = gridFixture().product;
    const r = render(
      <GfsStatus
        view={{
          state: 'current',
          now: GRID_RUN,
          selection: {
            vertical: { kind: 'pressure', pressure_pa: 50000 },
            horizon_hours: horizon as 0 | 6,
          },
          products: { winds: p },
        }}
      />
    );
    expect(r.container.textContent).toContain(
      horizon ? '500 hPa · +6 h' : '500 hPa · Now'
    );
    expect(r.container.querySelector('time, details, summary')).toBeNull();
    expect(r.container.textContent).not.toContain('Run ');
    expect(r.container.textContent).not.toContain('Valid ');
  }
);

it.each(['winds', 'temperature', 'both'] as const)(
  'keys only the admitted %s layer without adding selection controls',
  (layer) => {
    const p = gridFixture().product;
    const products: GfsProducts = {};
    if (layer !== 'temperature') products.winds = p;
    if (layer !== 'winds') products.temperature = p;
    const r = render(
      <GfsStatus view={{ state: 'stale', now: GRID_RUN, products }} />
    );
    expect(screen.getByLabelText('Atmosphere legend').textContent).toContain(
      'NOAA GFS'
    );
    expect(Boolean(screen.queryByText('Wind · kt'))).toBe(
      layer !== 'temperature'
    );
    expect(Boolean(screen.queryByText('Temperature · °C'))).toBe(
      layer !== 'winds'
    );
    if (layer !== 'winds') {
      expect(r.container.textContent).toContain('−80');
      expect(r.container.textContent).toContain('+40');
    }
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByRole('switch')).toBeNull();
  }
);

it('identifies the admitted flight level without interpolation instructions', () => {
  const p = gridFixture().product;
  p.vertical = {
    kind: 'flight-level',
    flight_level: 390,
    reference: 'pressure-altitude-1013.25hpa',
    derivation: 'isa-log-pressure-v1',
    source_pressures_pa: [15000, 20000],
  };
  render(
    <GfsStatus
      view={{ state: 'current', now: GRID_RUN, products: { winds: p } }}
    />
  );
  expect(screen.getByLabelText('Atmosphere legend').textContent).toContain(
    'FL390'
  );
  expect(screen.getByLabelText('Atmosphere legend').textContent).not.toContain(
    'interpolation'
  );
});
