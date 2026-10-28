/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { UtcDateTime } from './UtcDateTime';
afterEach(cleanup);
it('uses explicit Zulu 00–23 hours and 00–59 minutes rather than browser time controls', () => {
  const change = vi.fn();
  const { container } = render(
    <UtcDateTime label="Start" value={null} onChange={change} />
  );
  expect(container.querySelector('input[type="time"]')).toBeNull();
  const hour = screen.getByLabelText('Start hour (Zulu)');
  const minute = screen.getByLabelText('Start minute (Zulu)');
  expect([...hour.querySelectorAll('option')].map((o) => o.value)).toEqual([
    '',
    ...Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0')),
  ]);
  expect(minute.querySelectorAll('option')).toHaveLength(61);
  fireEvent.change(hour, { target: { value: '23' } });
  fireEvent.change(screen.getByLabelText('Start date (Zulu)'), {
    target: { value: '2026-10-28' },
  });
  fireEvent.change(minute, { target: { value: '59' } });
  expect(change).toHaveBeenLastCalledWith('2026-10-28T23:59:00Z');
});
it('preserves untouched microseconds and independently changes an overnight date', () => {
  function Example() {
    const [value, change] = useState<string | null>(
      '2026-10-28T23:59:12.123456Z'
    );
    return (
      <>
        <UtcDateTime label="End" value={value} onChange={change} />
        <output>{value}</output>
      </>
    );
  }
  render(<Example />);
  fireEvent.change(screen.getByLabelText('End minute (Zulu)'), {
    target: { value: '59' },
  });
  expect(screen.getByRole('status').textContent).toBe(
    '2026-10-28T23:59:12.123456Z'
  );
  fireEvent.change(screen.getByLabelText('End date (Zulu)'), {
    target: { value: '2026-10-29' },
  });
  fireEvent.change(screen.getByLabelText('End hour (Zulu)'), {
    target: { value: '00' },
  });
  expect(screen.getByRole('status').textContent).toBe('2026-10-29T00:59:00Z');
});
