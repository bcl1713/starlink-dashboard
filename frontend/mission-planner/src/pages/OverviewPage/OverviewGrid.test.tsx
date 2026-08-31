import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode, useState } from 'react';
import { describe, expect, it } from 'vitest';

import { OverviewGrid } from './OverviewGrid';
import { OverviewClocks } from './OverviewClocks';

type Listener = (event: MediaQueryListEvent) => void;

function installMatchMedia(width: number) {
  const records: {
    query: string;
    listeners: Set<Listener>;
    list: MediaQueryList;
    add: number;
    remove: number;
  }[] = [];

  const matches = (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)?.[1];
    const max = /max-width:\s*(\d+)px/.exec(query)?.[1];
    return (!min || width >= Number(min)) && (!max || width <= Number(max));
  };

  window.matchMedia = (query: string) => {
    const record = {
      query,
      listeners: new Set<Listener>(),
      add: 0,
      remove: 0,
      list: {
        media: query,
        matches: matches(query),
        onchange: null,
        addEventListener: (_type: string, listener: Listener) => {
          record.add += 1;
          record.listeners.add(listener);
        },
        removeEventListener: (_type: string, listener: Listener) => {
          record.remove += 1;
          record.listeners.delete(listener);
        },
        addListener: (listener: Listener) => record.listeners.add(listener),
        removeListener: (listener: Listener) =>
          record.listeners.delete(listener),
        dispatchEvent: () => true,
      } as MediaQueryList,
    };
    records.push(record);
    return record.list;
  };

  return {
    resize(nextWidth: number) {
      width = nextWidth;
      for (const record of records) {
        const next = matches(record.query);
        Object.defineProperty(record.list, 'matches', {
          configurable: true,
          value: next,
        });
        const event = { matches: next, media: record.query };
        for (const listener of record.listeners) {
          listener(event as MediaQueryListEvent);
        }
      }
    },
    listenerCount() {
      return records.reduce(
        (total, record) => total + record.listeners.size,
        0
      );
    },
    countsByQuery() {
      const counts = new Map<
        string,
        { add: number; remove: number; active: number }
      >();
      for (const record of records) {
        const count = counts.get(record.query) ?? {
          add: 0,
          remove: 0,
          active: 0,
        };
        count.add += record.add;
        count.remove += record.remove;
        count.active += record.listeners.size;
        counts.set(record.query, count);
      }
      return counts;
    },
  };
}

function StatefulSentinel() {
  const [value, setValue] = useState('');
  return (
    <label>
      Map sentinel
      <input value={value} onChange={(event) => setValue(event.target.value)} />
    </label>
  );
}

function grid(includeClocks = false) {
  return (
    <OverviewGrid
      map={<StatefulSentinel />}
      groundEntryPoint={
        <article>
          <h3>Ground entry point</h3>
          <p>Ground entry point sentinel</p>
        </article>
      }
      obstruction={
        <article>
          <h3>Obstruction</h3>
          <p>Obstruction sentinel</p>
        </article>
      }
      packetLoss={
        <article>
          <h3>Packet loss</h3>
          <p>Packet loss sentinel</p>
        </article>
      }
      poiQuickReference={
        <article>
          <h2>POI Quick Reference</h2>
          <p>POI sentinel</p>
        </article>
      }
      latency={
        includeClocks ? (
          <OverviewClocks
            clocks={[
              { id: 'utc', label: 'UTC (Zulu)', timeZone: 'UTC' },
              { id: 'tokyo', label: 'Tokyo', timeZone: 'Asia/Tokyo' },
            ]}
            expanded={true}
            layoutMode="desktop"
            now={new Date('2026-08-31T05:00:00.000Z')}
            onExpandedChange={() => {}}
          />
        ) : (
          <article>
            <h2>Network Latency</h2>
            <p>Latency sentinel</p>
          </article>
        )
      }
      throughput={
        <article>
          <h2>Throughput</h2>
          <p>Throughput sentinel</p>
        </article>
      }
    />
  );
}

describe('OverviewGrid', () => {
  it('contains every slot once in the semantic primary grid and right rail', () => {
    installMatchMedia(1280);
    render(grid());

    const primaryGrid = document.querySelector(
      '.overview-primary-grid'
    ) as HTMLElement | null;
    const summary = document.querySelector(
      '.overview-summary-region'
    ) as HTMLElement | null;
    const rightRail = document.querySelector(
      '.overview-right-rail'
    ) as HTMLElement | null;

    expect(primaryGrid).toContainElement(
      document.querySelector('.overview-map-region') as HTMLElement | null
    );
    expect(primaryGrid).toContainElement(summary);
    expect(rightRail).toContainElement(
      document.querySelector('.overview-poi-region') as HTMLElement | null
    );
    expect(rightRail).toContainElement(
      document.querySelector('.overview-latency-region') as HTMLElement | null
    );
    expect(rightRail).toContainElement(
      document.querySelector(
        '.overview-throughput-region'
      ) as HTMLElement | null
    );
    for (const text of [
      'Ground entry point sentinel',
      'Obstruction sentinel',
      'Packet loss sentinel',
      'POI sentinel',
      'Latency sentinel',
      'Throughput sentinel',
    ]) {
      expect(screen.getAllByText(text)).toHaveLength(1);
    }
  });

  it('renders the required heading hierarchy in document order', () => {
    installMatchMedia(390);
    render(grid());

    expect(
      screen.getByRole('heading', { level: 2, name: 'Current Position' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'Operational summaries' })
    ).toBeInTheDocument();

    const headings = screen.getAllByRole('heading').map((heading) => ({
      level: Number(heading.tagName.slice(1)),
      name: heading.textContent,
    }));
    expect(headings).toEqual([
      { level: 2, name: 'Current Position' },
      { level: 2, name: 'Operational summaries' },
      { level: 3, name: 'Ground entry point' },
      { level: 3, name: 'Obstruction' },
      { level: 3, name: 'Packet loss' },
      { level: 2, name: 'POI Quick Reference' },
      { level: 2, name: 'Network Latency' },
      { level: 2, name: 'Throughput' },
    ]);
  });

  it('preserves semantic order while exposing the current layout mode', () => {
    installMatchMedia(390);
    render(grid());

    const regions = screen.getAllByRole('region').map((region) => ({
      name: region.getAttribute('aria-label'),
      text: region.textContent,
    }));

    expect(regions.map((region) => region.name)).toEqual([
      'Current Position',
      'Operational summaries',
      'Operations right rail',
    ]);
    expect(regions[1].text).toContain('Ground entry point sentinel');
    expect(regions[1].text).toContain('Obstruction sentinel');
    expect(regions[1].text).toContain('Packet loss sentinel');
    expect(screen.getByTestId('overview-grid')).toHaveAttribute(
      'data-layout-mode',
      'mobile'
    );
  });

  it('balances exact StrictMode media listeners across all four layout queries', async () => {
    const media = installMatchMedia(390);
    const { unmount } = render(<StrictMode>{grid(true)}</StrictMode>);

    const input = screen.getByLabelText('Map sentinel');
    const mapChild = input.parentElement;
    const clock = screen.getByLabelText(/UTC \(Zulu\):/).closest('article');
    fireEvent.change(input, { target: { value: 'operator note' } });
    for (const count of media.countsByQuery().values()) {
      expect(count).toEqual({ add: 2, remove: 1, active: 1 });
    }

    for (const [width, mode] of [
      [768, 'tablet'],
      [1024, 'desktop'],
      [1536, 'wide'],
      [390, 'mobile'],
    ] as const) {
      media.resize(width);
      await waitFor(() =>
        expect(screen.getByTestId('overview-grid')).toHaveAttribute(
          'data-layout-mode',
          mode
        )
      );
      expect(screen.getByLabelText('Map sentinel')).toBe(input);
      expect(screen.getByLabelText('Map sentinel').parentElement).toBe(
        mapChild
      );
      expect(screen.getByLabelText(/UTC \(Zulu\):/).closest('article')).toBe(
        clock
      );
      expect(input).toHaveValue('operator note');
    }

    unmount();
    for (const count of media.countsByQuery().values()) {
      expect(count).toEqual({ add: 2, remove: 2, active: 0 });
    }
    expect(media.listenerCount()).toBe(0);
  });
});
