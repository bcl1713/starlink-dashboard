import { enterZulu } from '@/test/utc-controls';
/** @vitest-environment jsdom */
import { useState } from 'react';
import { record } from '@/test/operator-fixtures';
import type { CapabilityEditorDraft } from './CapabilityEditor';
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
  fireEvent.change(screen.getByLabelText('Functional Capability'), {
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

it('submits distinct functional and redundancy UTC observations and preserves the other dimension when time becomes unknown', () => {
  const save = vi.fn().mockResolvedValue(false);
  function Form() {
    const [draft, setDraft] = useState<CapabilityEditorDraft>({
      input: capabilityInput('mission-a'),
      version: null,
      currentDimensions: [],
    });
    return (
      <CapabilityForm
        draft={draft}
        onDraftChange={setDraft}
        disabled={false}
        asOf="2026-10-17T16:00:00Z"
        onSave={save}
      />
    );
  }
  render(<Form />);
  const change = (name: string, value: string) =>
    fireEvent.change(screen.getByLabelText(name), { target: { value } });
  change('Capability Name', 'Fictional audio service');
  change('Functional Capability', 'functional');
  fireEvent.click(
    screen.getByLabelText('Use Current Zulu for Functional Observation')
  );
  enterZulu('Functional Observation', '2026-10-17T15:00:00');
  change('Redundancy', 'unavailable');
  fireEvent.click(
    screen.getByLabelText('Use Current Zulu for Redundancy Observation')
  );
  enterZulu('Redundancy Observation', '2026-10-17T15:30:00');
  change('Redundancy Time Precision', 'approximate');
  fireEvent.click(screen.getByRole('button', { name: 'Save Assessment' }));
  expect(save.mock.calls[0][0].payload).toMatchObject({
    functional_status: 'functional',
    functional_observed_at: '2026-10-17T15:00:00.000Z',
    functional_time_precision: 'exact',
    redundancy_status: 'unavailable',
    redundancy_observed_at: '2026-10-17T15:30:00.000Z',
    redundancy_time_precision: 'approximate',
  });
  expect(save.mock.calls[0][2]).toEqual([]);
  change('Functional Time Precision', 'unknown');
  fireEvent.click(screen.getByRole('button', { name: 'Save Assessment' }));
  expect(save.mock.calls[1][0].payload).toMatchObject({
    functional_observed_at: null,
    functional_time_precision: 'unknown',
    redundancy_observed_at: '2026-10-17T15:30:00.000Z',
    redundancy_time_precision: 'approximate',
  });
});

it('retains an existing assessment payload and precise saved time when opening a correction', () => {
  const initial = capabilityInput('mission-a');
  initial.payload.title = 'Fictional existing assessment';
  initial.payload.note = 'Retained older operator detail';
  initial.time.planned_end_at = '2026-10-17T17:00:00.123456Z';
  const saved = { ...record, ...initial };
  const opened = capabilityInput('mission-a', saved);
  expect(opened.payload).toEqual(saved.payload);
  expect(opened.time).toEqual(saved.time);
  expect(opened.scope).toBe(saved.scope);
});
