import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SimulationRunPanel } from './SimulationRunPanel';
import { runningStatus, completedStatus } from '@/test/simulation-run-fixtures';
afterEach(cleanup);
it('labels simulation and shows confirmed progress and real runtime', () => {
  render(<SimulationRunPanel status={runningStatus()} stale={false} compact />);
  expect(screen.getByLabelText('Simulation run')).toHaveTextContent('10×');
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '10');
  expect(screen.getByText(/12.*120.*real seconds/)).toBeVisible();
});
it('keeps stale and terminal results explicit', () => {
  const view = render(
    <SimulationRunPanel status={runningStatus()} stale compact />
  );
  expect(screen.getByText(/Refresh unavailable/)).toBeVisible();
  view.rerender(
    <SimulationRunPanel status={completedStatus()} stale={false} compact />
  );
  expect(screen.getByLabelText('Simulation run')).toHaveTextContent(
    'Completed'
  );
});
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
