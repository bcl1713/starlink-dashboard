// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { RouteSigmetNotices } from './RouteSigmetNotices';
import { createSigmetPresentation } from './route-sigmet-presentation';
import { WeatherBudget } from './weather-budget';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import { routeSigmetSnapshotSchema } from '@/services/route-sigmets';
import { parseAviationFeatures } from '@/services/aviation-features';
import { NOW } from './fixtures';
vi.mock('@/hooks/api/useRouteSigmets', () => ({
  useRouteSigmets: () => ({
    snapshot: { context: { context_key: 'c' } },
    available: true,
  }),
  useSetSigmetAcknowledgement: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  }),
}));
afterEach(cleanup);
it('shows the concise count and lets users navigate every pending card', () => {
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
    expect(screen.getByText('SIGMETS: 4')).toBeDefined();
    expect(screen.queryByText(/pending route advisories/)).toBeNull();
    expect(screen.queryByText(/Coverage unknown/)).toBeNull();
    const first = screen.getAllByRole('article').map((n) => n.textContent);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Previous' })).not.toHaveProperty(
      'disabled',
      true
    );
    expect(first).toHaveLength(3);
    expect(screen.getByRole('button', { name: /Acknowledge/ })).toBeDefined();
  } finally {
    presentation.dispose();
    occupied.release();
  }
});
it('renders nothing for unavailable or unknown-only route results', () => {
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
  expect(screen.queryByLabelText('Route SIGMET advisories')).toBeNull();
  expect(screen.queryAllByRole('article')).toHaveLength(0);
  presentation.dispose();
});
