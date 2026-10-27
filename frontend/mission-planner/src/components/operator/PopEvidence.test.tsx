/** @vitest-environment jsdom */
import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { PopEvidenceView } from './PopEvidence';
import { projectGroundEntryLabel } from '@/pages/status-projection';
import type { StatusResponse } from '@/services/status';
afterEach(cleanup);
const status: StatusResponse = {
  timestamp: new Date().toISOString(),
  pop_observation: {
    ip: '216.255.181.42',
    status: 'known',
    source: 'live',
    freshness: 'fresh',
    sampled_at: '2035-01-01T12:00:00Z',
    lookup_at: '2035-01-01T11:59:00Z',
    entry: {
      ip: '216.255.181.42',
      city: 'Tokyo',
      country: 'JP',
      latitude: 35.6895,
      longitude: 139.69171,
      pop_id: 'tokyo',
      identity_source: 'operator_static_cidr',
      matched_cidr: '216.255.181.0/24',
      discrepancy: true,
      provider_geoip: {
        ip: '216.255.181.42',
        city: 'Invented Domestic City',
        country: 'US',
        latitude: 33,
        longitude: -84,
        freshness: 'fresh',
      },
    },
  },
};
it('presents canonical identity and contradictory provider evidence independently', () => {
  render(<PopEvidenceView status={status} />);
  expect(screen.getByLabelText('PoP evidence').textContent).toContain(
    'operator-supplied static CIDR mapping'
  );
  expect(screen.getByLabelText('PoP evidence').textContent).toContain('Tokyo');
  expect(screen.getByLabelText('PoP evidence').textContent).toContain(
    'Invented Domestic City'
  );
  expect(screen.getByLabelText('PoP evidence').textContent).toContain(
    'physical routing is unverified'
  );
  expect(projectGroundEntryLabel(status)).toBe('PoP · Tokyo');
});
it('uses a GeoIP map label for an unverified provider location', () => {
  const entry = status.pop_observation!.entry!;
  expect(
    projectGroundEntryLabel({
      ...status,
      pop_observation: {
        ...status.pop_observation!,
        entry: { ...entry, identity_source: 'geoip', pop_id: null },
      },
    })
  ).toBe('GeoIP · Tokyo');
});
