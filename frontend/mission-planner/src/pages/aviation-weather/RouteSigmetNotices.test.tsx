// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { RouteSigmetNotices } from './RouteSigmetNotices';
import { createSigmetPresentation } from './route-sigmet-presentation';
import { WeatherBudget } from './weather-budget';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import { routeSigmetSnapshotSchema } from '@/services/route-sigmets';
import { parseAviationFeatures } from '@/services/aviation-features';
import { NOW } from './fixtures';
afterEach(cleanup);
it('three_cards_and_overflow_without_dashboard_actions', () => {
  const fixture = routeSnapshot();
  fixture.snapshot.entries = [1, 4, 2, 3].map((order) => ({
    ...fixture.snapshot.entries[0],
    attention_order: order,
    notice_key: String(order).repeat(64),
    bulletin_key: String(order).repeat(64),
    feature_ids: ['advisory-' + order],
  }));
  fixture.data.features = [1, 4, 2, 3].map((order) => ({
    ...fixture.data.features[0],
    id: 'advisory-' + order,
  }));
  const budget = new WeatherBudget();
  const occupied = budget.reserve('occupied', {
    encoded: 0,
    decoded: 0,
    gpu: 16 * 1024 ** 2,
  });
  const source = {
    snapshot: routeSigmetSnapshotSchema.parse(fixture.snapshot),
    collection: parseAviationFeatures(fixture.data, 'sigmet'),
    available: true,
    error: null,
    dataLease: { retain: () => ({ release() {} }) },
    nowMs: NOW,
  };
  const presentation = createSigmetPresentation(
    {
      source,
      localContextKey: hash('c'),
      intersectingOnly: true,
      nowMs: NOW,
      routePoints: [],
    },
    budget
  );
  try {
    render(<RouteSigmetNotices presentation={presentation} />);
    expect(screen.getAllByRole('article')).toHaveLength(3);
    expect(screen.getByText(/4 pending/)).toBeDefined();
    expect(screen.getByText(/1 additional/)).toBeDefined();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(
      screen.getAllByText(/Altitude and passage-time match not evaluated/)
    ).toHaveLength(3);
    expect(screen.getAllByText(/Route segment 1/)).toHaveLength(3);
    expect(screen.getAllByText(/Vertical bounds unknown/)).toHaveLength(3);
    expect(screen.getByText(/Highlight unavailable/)).toBeDefined();
    expect(screen.getAllByText(/2026-10-06T12:00:00.000 UTC/)).toHaveLength(3);
  } finally {
    presentation.dispose();
    occupied.release();
  }
});
it('states route unavailable and unknown coverage without claiming a clear route', () => {
  const presentation = createSigmetPresentation(
    {
      source: {
        snapshot: null,
        collection: null,
        available: false,
        error: null,
        dataLease: null,
        nowMs: NOW,
      },
      localContextKey: null,
      intersectingOnly: true,
      nowMs: NOW,
      routePoints: [],
    },
    new WeatherBudget()
  );
  render(<RouteSigmetNotices presentation={presentation} />);
  expect(screen.getByText(/Route unavailable/)).toBeDefined();
  expect(screen.queryByText(/^0 pending/)).toBeNull();
  expect(screen.getByText(/Coverage unknown or partial/)).toBeDefined();
  expect(screen.queryAllByRole('article')).toHaveLength(0);
  presentation.dispose();
});
