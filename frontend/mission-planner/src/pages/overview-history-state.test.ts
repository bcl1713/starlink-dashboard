import { describe, expect, it } from 'vitest';
import { overviewHistoryState } from './overview-history-state';
describe('overviewHistoryState', () => {
  it('reports an unavailable history source rather than no aircraft movement', () => {
    expect(
      overviewHistoryState({
        isLoading: false,
        isError: true,
        pointCount: 0,
      })
    ).toBe('Aircraft history unavailable');
  });
  it('reports loading history distinctly from an empty successful trail', () => {
    expect(
      overviewHistoryState({
        isLoading: true,
        isError: false,
        pointCount: 0,
      })
    ).toBe('Loading aircraft history…');
    expect(
      overviewHistoryState({
        isLoading: false,
        isError: false,
        pointCount: 0,
      })
    ).toBe('No aircraft history');
  });
  it('reports the available trail point count', () => {
    expect(
      overviewHistoryState({
        isLoading: false,
        isError: false,
        pointCount: 2,
      })
    ).toBe('2 trail points');
  });
});
