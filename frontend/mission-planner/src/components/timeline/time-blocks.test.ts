import { expect, it } from 'vitest';
import { timeBlocks } from './time-blocks';

it('combines consecutive equal statuses while retaining changes and gaps', () => {
  const rows = [
    {
      start: '2035-01-01T00:00:00Z',
      end: '2035-01-01T00:01:00Z',
      status: 'up',
    },
    {
      start: '2035-01-01T00:01:00Z',
      end: '2035-01-01T00:02:00Z',
      status: 'up',
    },
    {
      start: '2035-01-01T00:02:00Z',
      end: '2035-01-01T00:03:00Z',
      status: 'down',
    },
    {
      start: '2035-01-01T00:04:00Z',
      end: '2035-01-01T00:05:00Z',
      status: 'down',
    },
  ];
  expect(
    timeBlocks(
      rows,
      (row) => row.start,
      (row) => row.end,
      (row) => row.status,
      (row, end) => ({ ...row, end })
    )
  ).toEqual([{ ...rows[0], end: rows[1].end }, rows[2], rows[3]]);
  expect(rows[0].end).toBe('2035-01-01T00:01:00Z');
});
