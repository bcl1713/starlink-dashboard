/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { health } from '@/test/operator-fixtures';
import * as api from '@/services/operator';
import { OperatorStoreSetup } from './OperatorStoreSetup';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('requires an explicit action for a pristine current simulation namespace', async () => {
  const provision = vi
    .spyOn(api, 'provisionOperatorStore')
    .mockResolvedValue(health);
  const refresh = vi.fn();
  render(
    <OperatorStoreSetup
      health={{
        ...health,
        source_mode: 'simulation',
        simulation_run_id: 'run-a',
        ready: false,
        error_code: 'store_initialization_required',
      }}
      refresh={refresh}
    />
  );
  expect(provision).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Initialize simulation journal' })
  );
  await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  expect(provision).toHaveBeenCalledWith(
    expect.objectContaining({
      source_mode: 'simulation',
      simulation_run_id: 'run-a',
    })
  );
});
it.each([
  'store_recovery_required',
  'store_corrupt',
  'store_mode_mismatch',
  'store_identity_mismatch',
  'simulation_run_required',
  'invalid_configuration',
])('does not offer initialization for %s', (code) => {
  const provision = vi.spyOn(api, 'provisionOperatorStore');
  render(
    <OperatorStoreSetup
      health={{ ...health, ready: false, error_code: code }}
      refresh={vi.fn()}
    />
  );
  expect(screen.queryByRole('button', { name: /^Initialize/ })).toBeNull();
  expect(
    screen.getByRole('link', { name: 'Operator setup and recovery' })
  ).toBeTruthy();
  expect(provision).not.toHaveBeenCalled();
});
it('healthy journal does not block unrelated CRUD because optional model inputs are absent', () => {
  const result = render(
    <OperatorStoreSetup health={health} refresh={vi.fn()} />
  );
  expect(result.container.textContent).toBe('');
});
