/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { page, record } from '@/test/operator-fixtures';
import { JournalList } from './JournalList';
afterEach(cleanup);
it.each([
  ['2026-10-28T23:59:12.123456Z', '2026-10-28 23:59 Zulu'],
  ['2026-10-29T00:00:00Z', '2026-10-29 00:00 Zulu'],
  [null, 'Occurrence time unknown'],
] as const)(
  'presents %s in Zulu and retains exact occurrence evidence in secondary details',
  (occurred_at, label) => {
    const saved = {
      ...record,
      time: {
        ...record.time,
        occurred_at,
        precision: occurred_at
          ? ('approximate' as const)
          : ('unknown' as const),
      },
    };
    const before = structuredClone(saved);
    render(
      <JournalList
        items={page([saved]).items}
        disabled={false}
        onEdit={vi.fn()}
        onHistory={vi.fn()}
        onTransition={vi.fn()}
      />
    );
    expect(screen.getByText(label).closest('details')).toBeNull();
    const details = screen.getByText('Timestamp Details').closest('details')!;
    expect(details.open).toBe(false);
    if (occurred_at)
      expect(screen.getByText(occurred_at).closest('details')).toBe(details);
    fireEvent.click(screen.getByText('Timestamp Details'));
    expect(details.textContent).toContain(occurred_at ?? 'Unknown');
    expect(details.textContent).toContain(saved.time.precision);
    expect(saved).toEqual(before);
  }
);
