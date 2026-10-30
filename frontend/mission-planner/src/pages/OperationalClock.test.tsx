/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OperationalClock } from './OperationalClock';
afterEach(() => {
  cleanup();
});
describe('OperationalClock', () => {
  it('shows the configured label and a 24-hour local time', () => {
    render(
      <OperationalClock
        label="Zulu / UTC"
        timeZone="UTC"
        currentTime={Date.UTC(2026, 0, 2, 0, 5, 6)}
      />
    );
    expect(screen.getByText('Zulu / UTC')).not.toBeNull();
    expect(screen.getByText('00:05:06')).not.toBeNull();
  });
  it('shows a configured local clock without labeling it Zulu', () => {
    render(
      <OperationalClock
        label="Washington, DC"
        timeZone="America/New_York"
        currentTime={Date.UTC(2026, 6, 2, 0, 5, 6)}
      />
    );
    expect(screen.getByText('Washington, DC')).not.toBeNull();
    expect(screen.getByText('20:05:06')).not.toBeNull();
    expect(screen.queryByText('Zulu')).toBeNull();
  });
});
