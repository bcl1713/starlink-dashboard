/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { enterZulu } from '@/test/utc-controls';
import { KaOutageConfig } from './KaOutageConfig';
import { KuOutageConfig } from './KuOutageConfig';
afterEach(cleanup);
it('captures a Ka start in Zulu and calculates its end across midnight', () => {
  const save = vi.fn();
  render(<KaOutageConfig outages={[]} onOutagesChange={save} />);
  enterZulu('Ka outage start', '2026-10-28T23:30');
  fireEvent.change(screen.getByLabelText('Duration (hours)'), {
    target: { value: '2' },
  });
  expect(
    screen.getByLabelText('Calculated Ka outage end time').textContent
  ).toContain('10/29/2026, 01:30:00 Zulu');
  fireEvent.click(screen.getByRole('button', { name: 'Add' }));
  expect(save.mock.calls[0][0][0]).toMatchObject({
    start_time: '2026-10-28T23:30:00.000Z',
    duration_seconds: 7200,
  });
});
it('captures explicit overnight Ku start and end dates', () => {
  const save = vi.fn();
  render(<KuOutageConfig outages={[]} onOutagesChange={save} />);
  enterZulu('Ku outage start', '2026-10-28T23:30');
  enterZulu('Ku outage end', '2026-10-29T00:30');
  fireEvent.click(screen.getByRole('button', { name: 'Add' }));
  expect(save.mock.calls[0][0][0]).toMatchObject({
    start_time: '2026-10-28T23:30:00.000Z',
    duration_seconds: 3600,
  });
});
