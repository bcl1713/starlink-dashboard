import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { SimulateLegDialog } from './SimulateLegDialog';
import { preview, runningStatus } from '@/test/simulation-run-fixtures';
import { simulationRunApi } from '@/services/simulation-run';
const mocks = vi.hoisted(() => ({
  activate: vi.fn(),
  mode: 'simulation',
  error: false,
}));
vi.mock('@/hooks/api/useSimulationRun', () => ({
  useSimulationRun: () => ({ data: { service_mode: mocks.mode } }),
}));
vi.mock('@/hooks/api/useMissions', () => ({
  useActivateLeg: () => ({ mutateAsync: mocks.activate, isPending: false }),
}));
afterEach(cleanup);
beforeEach(() => {
  mocks.mode = 'simulation';
  mocks.activate
    .mockReset()
    .mockResolvedValue({ simulation_run: runningStatus() });
});
function mount() {
  return render(
    <SimulateLegDialog
      missionId="mission-1"
      legId="leg-1"
      open
      onOpenChange={vi.fn()}
    />
  );
}
it('submits only the selected mode after a current preview', async () => {
  vi.spyOn(simulationRunApi, 'preview').mockResolvedValue({
    ...preview,
    pacing: { mode: 'target_runtime', runtime_seconds: 120 },
  });
  mount();
  fireEvent.click(screen.getByLabelText('Target runtime'));
  fireEvent.change(screen.getByLabelText('Runtime seconds'), {
    target: { value: '120' },
  });
  expect(
    screen.getByRole('button', { name: 'Start simulation' })
  ).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Start simulation' })
    ).toBeEnabled()
  );
  fireEvent.click(screen.getByRole('button', { name: 'Start simulation' }));
  await waitFor(() =>
    expect(mocks.activate).toHaveBeenCalledWith({
      missionId: 'mission-1',
      legId: 'leg-1',
      simulation: {
        pacing: { mode: 'target_runtime', runtime_seconds: 120 },
        plan_token: preview.plan_token,
      },
    })
  );
});
it('ignores obsolete preview responses after changing the input', async () => {
  let resolve!: (value: typeof preview) => void;
  vi.spyOn(simulationRunApi, 'preview').mockReturnValue(
    new Promise((done) => {
      resolve = done;
    })
  );
  mount();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  fireEvent.change(screen.getByLabelText('Multiplier'), {
    target: { value: '2' },
  });
  resolve(preview);
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Preview' })).toBeEnabled()
  );
  expect(
    screen.getByRole('button', { name: 'Start simulation' })
  ).toBeDisabled();
});
it('keeps the draft on failed start and shows a retryable error', async () => {
  vi.spyOn(simulationRunApi, 'preview').mockResolvedValue(preview);
  mocks.activate.mockRejectedValue(new Error('Plan changed; preview again'));
  mount();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Start simulation' })
    ).toBeEnabled()
  );
  fireEvent.click(screen.getByRole('button', { name: 'Start simulation' }));
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Plan changed')
  );
  expect(screen.getByLabelText('Multiplier')).toHaveValue(10);
});
it('invalidates a successful preview when the leg changes', async () => {
  vi.spyOn(simulationRunApi, 'preview').mockResolvedValue(preview);
  const view = mount();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Start simulation' })
    ).toBeEnabled()
  );
  view.rerender(
    <SimulateLegDialog
      missionId="mission-1"
      legId="leg-2"
      open
      onOpenChange={vi.fn()}
    />
  );
  expect(
    screen.getByRole('button', { name: 'Start simulation' })
  ).toBeDisabled();
});
it('supports keyboard form submission without duplicate starts', async () => {
  vi.spyOn(simulationRunApi, 'preview').mockResolvedValue(preview);
  let finish!: () => void;
  mocks.activate.mockReturnValue(
    new Promise<void>((resolve) => {
      finish = resolve;
    })
  );
  mount();
  const form = screen.getByLabelText('Multiplier').closest('form')!;
  fireEvent.submit(form);
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Start simulation' })
    ).toBeEnabled()
  );
  fireEvent.submit(form);
  fireEvent.submit(form);
  expect(mocks.activate).toHaveBeenCalledTimes(1);
  finish();
});
it.each(['live', 'unknown'])('disables preview in %s mode', (mode) => {
  mocks.mode = mode;
  mount();
  expect(screen.getByRole('button', { name: 'Preview' })).toBeDisabled();
});
it('shows labeled field errors for out-of-range values', () => {
  mount();
  fireEvent.change(screen.getByLabelText('Multiplier'), {
    target: { value: '1001' },
  });
  expect(screen.getByLabelText('Multiplier')).toHaveAttribute(
    'aria-invalid',
    'true'
  );
  expect(screen.getByRole('button', { name: 'Preview' })).toBeDisabled();
});
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
