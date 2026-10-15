// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { parseRouteSigmetSnapshot } from '@/services/route-sigmets';
import { routeSnapshot } from '@/test/route-sigmet-fixtures';
import { SigmetEncounterDetails } from './SigmetEncounterDetails';
afterEach(cleanup);
it('keeps missing source and altitude assumptions explicit', () => {
  const entry = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  render(<SigmetEncounterDetails entry={entry} plan={null} />);
  expect(screen.getByText(/Missing waypoint times/)).toBeDefined();
  expect(screen.getByText(/Altitude is not evaluated/)).toBeDefined();
  expect(screen.getByText(/Precision: unknown/)).toBeDefined();
});
it('shows exact ISO passage without summary rounding', () => {
  const entry = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  const start = entry.valid_from_ms;
  entry.encounter = {
    spans: [
      {
        entry_ms: start + 1,
        exit_ms: start + 2,
        status: 'overlap',
        reason: null,
      },
    ],
    status: 'overlap',
    unknown_count: 0,
    reason: null,
  };
  render(<SigmetEncounterDetails entry={entry} plan={null} />);
  expect(
    screen.getByText((text) => text.includes(new Date(start + 1).toISOString()))
  ).toBeDefined();
});
