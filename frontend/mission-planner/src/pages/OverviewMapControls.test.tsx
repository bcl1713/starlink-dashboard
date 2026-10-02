/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { afterEach, it, expect } from 'vitest';
import { useState } from 'react';
import { OverviewMapControls } from './OverviewMapControls';
import type { OverviewCameraIntent } from './overview-camera-frame';
afterEach(cleanup);
function Controls({
  reason = null,
  intent = 'manual',
}: {
  reason?: string | null;
  intent?: OverviewCameraIntent;
}) {
  const [exploring, setExploring] = useState(false);
  return (
    <OverviewMapControls
      exploring={exploring}
      intent={intent}
      followUnavailable={reason}
      onExploreChange={setExploring}
      onReset={() => {}}
    />
  );
}
it('exits exploration on Escape and restores focus without trapping navigation', () => {
  render(<Controls />);
  fireEvent.click(screen.getByRole('button', { name: 'Explore map' }));
  expect(
    screen.getByRole('button', { name: 'Exit map exploration' })
  ).toHaveAttribute('aria-pressed', 'true');
  fireEvent.keyDown(window, { key: 'Escape' });
  expect(screen.getByRole('button', { name: 'Explore map' })).toHaveFocus();
  expect(screen.getByRole('button', { name: 'Explore map' })).toHaveAttribute(
    'aria-pressed',
    'false'
  );
});
it('keeps reset available without a position and explains paused configured following', () => {
  render(<Controls reason="Aircraft position stale" intent="follow" />);
  expect(
    screen.getByRole('button', { name: 'Reset map view' })
  ).not.toBeDisabled();
  expect(screen.getByRole('status').textContent).toBe(
    'Follow paused · Aircraft position stale'
  );
});
