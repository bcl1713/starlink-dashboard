import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { OverviewGrid, useOverviewLayoutMode } from './OverviewGrid';

type Listener = (event: MediaQueryListEvent) => void;

function installMatchMedia(width: number) {
  const records: {
    query: string;
    listeners: Set<Listener>;
    list: MediaQueryList;
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
      list: {
        media: query,
        matches: matches(query),
        onchange: null,
        addEventListener: (_type: string, listener: Listener) => {
          record.listeners.add(listener);
        },
        removeEventListener: (_type: string, listener: Listener) => {
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
  };
}

function ModeProbe() {
  return <output aria-label="layout mode">{useOverviewLayoutMode()}</output>;
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

function grid() {
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
        <article>
          <h2>Network Latency</h2>
          <p>Latency sentinel</p>
        </article>
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

  it('transitions modes without remounting children or losing input state', async () => {
    const media = installMatchMedia(390);
    const { rerender } = render(
      <>
        <ModeProbe />
        {grid()}
      </>
    );

    const input = screen.getByLabelText('Map sentinel');
    input.focus();
    input.setAttribute('data-owned-node', 'stable');
    fireEvent.change(input, { target: { value: 'operator note' } });

    for (const [width, mode] of [
      [768, 'tablet'],
      [1024, 'desktop'],
      [1536, 'wide'],
      [767, 'mobile'],
    ] as const) {
      media.resize(width);
      await waitFor(() =>
        expect(screen.getByLabelText('layout mode')).toHaveTextContent(mode)
      );
      rerender(
        <>
          <ModeProbe />
          {grid()}
        </>
      );
      expect(screen.getByLabelText('Map sentinel')).toBe(input);
      expect(screen.getByLabelText('Map sentinel')).toHaveAttribute(
        'data-owned-node',
        'stable'
      );
    }

    expect(media.listenerCount()).toBeGreaterThan(0);
    expect(screen.getByLabelText('Map sentinel')).toHaveValue('operator note');
  });
});
