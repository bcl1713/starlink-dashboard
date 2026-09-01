import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode, useState } from 'react';
import { describe, expect, it } from 'vitest';

import { useOverviewLayoutMode } from './overview-layout';
import { OverviewLayoutProvider } from './overview-layout-provider';

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

function ModeConsumer({ label }: { readonly label: string }) {
  const mode = useOverviewLayoutMode();
  const [value, setValue] = useState('');
  return (
    <label>
      {label}
      <output aria-label={`${label} mode`}>{mode}</output>
      <input
        aria-label={`${label} note`}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
    </label>
  );
}

function NestedProviderHarness() {
  const [showNested, setShowNested] = useState(true);
  return (
    <OverviewLayoutProvider>
      <ModeConsumer label="Outer" />
      <button type="button" onClick={() => setShowNested(false)}>
        Remove nested
      </button>
      {showNested ? (
        <OverviewLayoutProvider>
          <ModeConsumer label="Inner" />
        </OverviewLayoutProvider>
      ) : null}
    </OverviewLayoutProvider>
  );
}

describe('OverviewLayoutProvider', () => {
  it('reuses ancestor layout context for nested providers', async () => {
    const media = installMatchMedia(390);
    const { unmount } = render(
      <StrictMode>
        <NestedProviderHarness />
      </StrictMode>
    );

    const outerInput = screen.getByLabelText('Outer note');
    const innerInput = screen.getByLabelText('Inner note');
    fireEvent.change(outerInput, { target: { value: 'outer stable' } });
    fireEvent.change(innerInput, { target: { value: 'inner stable' } });

    for (const count of media.countsByQuery().values()) {
      expect(count).toEqual({ add: 2, remove: 1, active: 1 });
    }
    expect(media.listenerCount()).toBe(4);

    for (const [width, mode] of [
      [768, 'tablet'],
      [1024, 'desktop'],
      [1536, 'wide'],
      [390, 'mobile'],
    ] as const) {
      media.resize(width);
      await waitFor(() =>
        expect(screen.getByLabelText('Outer mode')).toHaveTextContent(mode)
      );
      expect(screen.getByLabelText('Inner mode')).toHaveTextContent(mode);
      expect(screen.getByLabelText('Outer note')).toBe(outerInput);
      expect(screen.getByLabelText('Inner note')).toBe(innerInput);
      expect(outerInput).toHaveValue('outer stable');
      expect(innerInput).toHaveValue('inner stable');
    }

    fireEvent.click(screen.getByRole('button', { name: 'Remove nested' }));
    expect(screen.queryByLabelText('Inner mode')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Outer mode')).toHaveTextContent('mobile');
    expect(screen.getByLabelText('Outer note')).toBe(outerInput);
    expect(outerInput).toHaveValue('outer stable');
    for (const count of media.countsByQuery().values()) {
      expect(count).toEqual({ add: 2, remove: 1, active: 1 });
    }

    unmount();
    for (const count of media.countsByQuery().values()) {
      expect(count).toEqual({ add: 2, remove: 2, active: 0 });
    }
    expect(media.listenerCount()).toBe(0);
  });
});
