import { render, screen, waitFor } from '@testing-library/react';
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
      groundEntryPoint={<p>Ground entry point sentinel</p>}
      obstruction={<p>Obstruction sentinel</p>}
      packetLoss={<p>Packet loss sentinel</p>}
      poiQuickReference={<p>POI sentinel</p>}
      latency={<p>Latency sentinel</p>}
      throughput={<p>Throughput sentinel</p>}
    />
  );
}

describe('OverviewGrid', () => {
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
      'POI Quick Reference',
      'Network Latency',
      'Throughput',
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
    input.dispatchEvent(new Event('input', { bubbles: true }));
    (input as HTMLInputElement).value = 'operator note';
    input.dispatchEvent(new Event('input', { bubbles: true }));

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
  });
});
