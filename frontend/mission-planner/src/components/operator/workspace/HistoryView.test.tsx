/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { HistoryView } from './HistoryView';
import { page, record } from '@/test/operator-fixtures';
afterEach(cleanup);
it('searches only loaded records and keeps removed records available for restoration and audit', () => {
  render(
    <HistoryView
      items={
        page([
          {
            ...record,
            deleted: true,
            payload: { ...record.payload, title: 'Synthetic removed' },
          },
          {
            ...record,
            record_id: 'other',
            payload: { ...record.payload, title: 'Other' },
          },
        ]).items
      }
      incomplete
      disabled={false}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onTransition={vi.fn()}
    />
  );
  fireEvent.change(screen.getByLabelText('Search loaded records'), {
    target: { value: 'Synthetic' },
  });
  expect(
    screen.getByRole('button', { name: 'Restore Synthetic removed' })
  ).toBeTruthy();
  expect(screen.queryByText('Other')).toBeNull();
  expect(screen.getByText(/Search covers loaded records only/)).toBeTruthy();
});
