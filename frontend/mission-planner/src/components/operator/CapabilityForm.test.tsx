/** @vitest-environment jsdom */
import { capabilityInput } from './capabilityInput';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CapabilityForm } from './CapabilityEditor';
afterEach(cleanup);
it('retains independent observation controls in the supplied draft', () => {
  const changed = vi.fn();
  const input = capabilityInput('mission-a');
  input.payload.redundancy_observed_at = '2026-10-17T12:00:00Z';
  input.payload.redundancy_time_precision = 'exact';
  render(
    <CapabilityForm
      draft={{ input, version: null, currentDimensions: [] }}
      onDraftChange={changed}
      disabled={false}
      asOf={null}
      onSave={vi.fn()}
    />
  );
  fireEvent.change(screen.getByLabelText('Functional capability'), {
    target: { value: 'degraded' },
  });
  expect(changed.mock.calls[0][0]).toMatchObject({
    input: {
      payload: {
        functional_status: 'degraded',
        redundancy_observed_at: '2026-10-17T12:00:00Z',
      },
    },
    currentDimensions: ['functional'],
  });
});
