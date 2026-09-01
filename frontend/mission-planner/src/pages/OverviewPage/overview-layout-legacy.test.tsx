import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { StrictMode, useState } from 'react';
import { describe, expect, it } from 'vitest';

import { OverviewGrid } from './OverviewGrid';
import { useOverviewLayoutMode } from './overview-layout';
import { OverviewLayoutProvider } from './overview-layout-provider';

const LAYOUT_QUERIES = [
  '(min-width: 1536px)',
  '(min-width: 1024px) and (max-width: 1535px)',
  '(min-width: 768px) and (max-width: 1023px)',
  '(max-width: 767px)',
] as const;

type LayoutQuery = (typeof LAYOUT_QUERIES)[number];
type LayoutMode = 'mobile' | 'tablet' | 'desktop' | 'wide';
type QueryApi = 'modern' | 'legacy';
type LayoutEvent = { readonly matches: boolean; readonly media: string };
type LayoutListener = (event: LayoutEvent) => void;
type Counts = {
  readonly modernAdd: number;
  readonly modernRemove: number;
  readonly legacyAdd: number;
  readonly legacyRemove: number;
  readonly active: number;
};

function installTrackedMedia(width: number, apiForQuery: QueryApi[]) {
  const records: Array<{
    readonly query: LayoutQuery;
    readonly api: QueryApi;
    readonly listeners: Set<LayoutListener>;
    modernAdd: number;
    modernRemove: number;
    legacyAdd: number;
    legacyRemove: number;
  }> = [];

  const matches = (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)?.[1];
    const max = /max-width:\s*(\d+)px/.exec(query)?.[1];
    return (!min || width >= Number(min)) && (!max || width <= Number(max));
  };

  const matchMedia = (query: string) => {
    const queryIndex = LAYOUT_QUERIES.indexOf(query as LayoutQuery);
    const api = apiForQuery[queryIndex] ?? 'modern';
    const record = {
      query: query as LayoutQuery,
      api,
      listeners: new Set<LayoutListener>(),
      modernAdd: 0,
      modernRemove: 0,
      legacyAdd: 0,
      legacyRemove: 0,
    };
    records.push(record);
    const list =
      api === 'modern'
        ? {
            media: query,
            addEventListener: (_type: 'change', listener: LayoutListener) => {
              record.modernAdd += 1;
              record.listeners.add(listener);
            },
            removeEventListener: (
              _type: 'change',
              listener: LayoutListener
            ) => {
              record.modernRemove += 1;
              record.listeners.delete(listener);
            },
          }
        : {
            media: query,
            addListener: (listener: LayoutListener) => {
              record.legacyAdd += 1;
              record.listeners.add(listener);
            },
            removeListener: (listener: LayoutListener) => {
              record.legacyRemove += 1;
              record.listeners.delete(listener);
            },
          };
    Object.defineProperty(list, 'matches', {
      configurable: true,
      get() {
        return matches(query);
      },
    });
    return list;
  };
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: matchMedia,
  });

  return {
    resize(nextWidth: number) {
      width = nextWidth;
      for (const record of records) {
        const event = { matches: matches(record.query), media: record.query };
        for (const listener of record.listeners) listener(event);
      }
    },
    countsByQuery() {
      return Object.fromEntries(
        LAYOUT_QUERIES.map((query) => {
          const matchingRecords = records.filter(
            (record) => record.query === query
          );
          return [
            query,
            {
              modernAdd: matchingRecords.reduce(
                (total, record) => total + record.modernAdd,
                0
              ),
              modernRemove: matchingRecords.reduce(
                (total, record) => total + record.modernRemove,
                0
              ),
              legacyAdd: matchingRecords.reduce(
                (total, record) => total + record.legacyAdd,
                0
              ),
              legacyRemove: matchingRecords.reduce(
                (total, record) => total + record.legacyRemove,
                0
              ),
              active: matchingRecords.reduce(
                (total, record) => total + record.listeners.size,
                0
              ),
            },
          ];
        })
      ) as Record<LayoutQuery, Counts>;
    },
    liveListenerCount() {
      return records.reduce(
        (total, record) => total + record.listeners.size,
        0
      );
    },
  };
}

function Consumer() {
  const mode = useOverviewLayoutMode();
  return <output aria-label="hook mode">{mode}</output>;
}

function Harness() {
  const [showNested, setShowNested] = useState(true);
  const [note, setNote] = useState('');
  return (
    <OverviewLayoutProvider>
      <OverviewGrid
        map={<span>map</span>}
        groundEntryPoint={<span>ground</span>}
        obstruction={<span>obstruction</span>}
        packetLoss={<span>packet</span>}
        poiQuickReference={<span>poi</span>}
        latency={<span>latency</span>}
        throughput={<span>throughput</span>}
      />
      <Consumer />
      <input
        aria-label="Layout note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <button type="button" onClick={() => setShowNested(false)}>
        Remove nested
      </button>
      {showNested ? (
        <OverviewLayoutProvider>
          <Consumer />
        </OverviewLayoutProvider>
      ) : null}
    </OverviewLayoutProvider>
  );
}

function expectCounts(
  media: ReturnType<typeof installTrackedMedia>,
  apiForQuery: QueryApi[],
  expected: {
    readonly add: number;
    readonly remove: number;
    readonly active: number;
  }
) {
  const counts = media.countsByQuery();
  LAYOUT_QUERIES.forEach((query, index) => {
    const api = apiForQuery[index];
    if (api === 'modern') {
      expect(counts[query]).toEqual({
        modernAdd: expected.add,
        modernRemove: expected.remove,
        legacyAdd: 0,
        legacyRemove: 0,
        active: expected.active,
      });
      return;
    }
    expect(counts[query]).toEqual({
      modernAdd: 0,
      modernRemove: 0,
      legacyAdd: expected.add,
      legacyRemove: expected.remove,
      active: expected.active,
    });
  });
}

describe('OverviewLayoutProvider legacy media listeners', () => {
  it('uses legacy listeners once per query under StrictMode and cleans them up', async () => {
    const apis: QueryApi[] = ['legacy', 'legacy', 'legacy', 'legacy'];
    const media = installTrackedMedia(390, apis);
    const rendered = render(
      <StrictMode>
        <Harness />
      </StrictMode>
    );
    const note = screen.getByLabelText('Layout note');
    fireEvent.change(note, { target: { value: 'stable' } });

    expectCounts(media, apis, { add: 2, remove: 1, active: 1 });
    expect(media.liveListenerCount()).toBe(4);
    for (const [width, mode] of [
      [768, 'tablet'],
      [1024, 'desktop'],
      [1536, 'wide'],
      [390, 'mobile'],
    ] as const satisfies readonly (readonly [number, LayoutMode])[]) {
      act(() => media.resize(width));
      await waitFor(() =>
        expect(screen.getByTestId('overview-grid')).toHaveAttribute(
          'data-layout-mode',
          mode
        )
      );
      expect(screen.getAllByLabelText('hook mode')[0]).toHaveTextContent(mode);
      expect(screen.getAllByLabelText('hook mode')[1]).toHaveTextContent(mode);
      expect(screen.getByLabelText('Layout note')).toBe(note);
      expect(note).toHaveValue('stable');
    }

    rendered.rerender(
      <StrictMode>
        <Harness />
      </StrictMode>
    );
    expectCounts(media, apis, { add: 2, remove: 1, active: 1 });
    fireEvent.click(screen.getByRole('button', { name: 'Remove nested' }));
    expect(screen.getAllByLabelText('hook mode')).toHaveLength(1);
    expectCounts(media, apis, { add: 2, remove: 1, active: 1 });
    rendered.unmount();
    expectCounts(media, apis, { add: 2, remove: 2, active: 0 });
    expect(media.liveListenerCount()).toBe(0);
  });

  it('pairs modern and legacy cleanup per media query', () => {
    const apis: QueryApi[] = ['modern', 'legacy', 'modern', 'legacy'];
    const media = installTrackedMedia(1024, apis);
    const rendered = render(
      <StrictMode>
        <Harness />
      </StrictMode>
    );

    expectCounts(media, apis, { add: 2, remove: 1, active: 1 });
    rendered.unmount();
    expectCounts(media, apis, { add: 2, remove: 2, active: 0 });
  });
});
