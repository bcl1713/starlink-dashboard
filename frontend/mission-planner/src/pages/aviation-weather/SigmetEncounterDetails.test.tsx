// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { parseRouteSigmetSnapshot } from '@/services/route-sigmets';
import { routeSnapshot } from '@/test/route-sigmet-fixtures';
import { SigmetEncounterDetails } from './SigmetEncounterDetails';
import { AviationReport } from './AviationReport';
import { advisory, collection, NOW } from './fixtures';
import { parseAviationFeatures } from '@/services/aviation-features';
afterEach(cleanup);
it('shows operational timing without implementation or altitude disclaimers', () => {
  const entry = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  const { container } = render(
    <SigmetEncounterDetails entry={entry} nowMs={NOW} />
  );
  expect(screen.getByText('Crossing time unknown')).toBeDefined();
  expect(container.textContent).not.toMatch(
    /revision|precision|method|segment-linear|altitude|source/i
  );
});
it('shows readable UTC crossing times without ISO milliseconds or hashes', () => {
  const entry = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  entry.encounter = {
    spans: [
      {
        entry_ms: NOW + 60000,
        exit_ms: NOW + 120000,
        status: 'overlap',
        reason: null,
      },
    ],
    status: 'overlap',
    unknown_count: 0,
    reason: null,
  };
  const { container } = render(
    <SigmetEncounterDetails entry={entry} nowMs={NOW} />
  );
  expect(container.textContent).toContain('Crossing expected');
  expect(container.textContent).toContain('UTC');
  expect(container.textContent).not.toMatch(
    /T\d\d:|\.000Z|revision|precision|method/i
  );
});
it('keeps hazard validity and original bulletin without identity bookkeeping', () => {
  const feature = parseAviationFeatures(collection([advisory()]), 'sigmet')
    .features[0];
  const { container } = render(<AviationReport feature={feature} now={NOW} />);
  expect(container.textContent).toContain('Valid');
  expect(container.textContent).toContain('Original bulletin');
  expect(container.textContent).not.toMatch(
    /canonical series|provider series|revision|Not cancelled|cancellation target/
  );
});

it('retains reported flight-level bounds as useful flight information', () => {
  const input = advisory();
  const feature = parseAviationFeatures(
    collection([
      {
        ...input,
        properties: {
          ...input.properties,
          vertical: {
            lower: 180,
            upper: 340,
            unit: 'flight-level',
            reference: 'FL',
          },
        },
      },
    ]),
    'sigmet'
  ).features[0];
  const { container } = render(<AviationReport feature={feature} now={NOW} />);
  expect(container.textContent).toContain('FL180–FL340');
  expect(container.textContent).not.toMatch(
    /not evaluated|not considered|precision|method|revision/
  );
});

it('states missing timing once rather than repeating it for every segment', () => {
  const entry = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  entry.spans = Array.from({ length: 3 }, (_, segment_index) => ({
    ...entry.spans[0],
    segment_index,
  }));
  entry.encounter.spans = Array.from({ length: 3 }, () => ({
    ...entry.encounter.spans[0],
  }));
  entry.encounter.unknown_count = 3;
  render(<SigmetEncounterDetails entry={entry} nowMs={NOW} />);
  expect(screen.getAllByText('Crossing time unknown')).toHaveLength(1);
});
