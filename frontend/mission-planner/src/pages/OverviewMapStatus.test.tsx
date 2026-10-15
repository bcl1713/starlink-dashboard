/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OverviewMapStatus } from './OverviewMapStatus';
afterEach(cleanup);
describe('map operational exceptions', () => {
  it('keeps normal planning state out of exception announcements', () => {
    render(<OverviewMapStatus messages={[]} />);
    expect(screen.queryByLabelText('Map status')).toBeNull();
  });
  it('provides non-color warning semantics separately from a legend', () => {
    render(
      <OverviewMapStatus
        messages={['No active route.', 'Planned link warning']}
      />
    );
    expect(screen.getByRole('status').textContent).toContain(
      'No active route.'
    );
    expect(screen.getByRole('status').textContent).toContain(
      'configured forbidden-azimuth rule'
    );
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
