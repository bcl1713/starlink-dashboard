import { describe, expect, it, vi } from 'vitest';
import { OVERVIEW_POI_FILTER_OPTIONS } from '../../types/monitoring';
import {
  addOverviewClock,
  createDefaultOverviewPreferences,
  loadOverviewPreferences,
  moveOverviewClock,
  OVERVIEW_PREFERENCES_STORAGE_KEY,
  OVERVIEW_PREFERENCES_VERSION,
  OVERVIEW_REFRESH_OPTIONS,
  relabelOverviewClock,
  removeOverviewClock,
  saveOverviewPreferences,
  type OverviewStorage,
} from './preferences';

function memoryStorage(value: string | null = null): OverviewStorage & {
  value: string | null;
} {
  return {
    value,
    getItem() {
      return this.value;
    },
    setItem(_key, next) {
      this.value = next;
    },
  };
}

function expectDeepFrozen(value: unknown): void {
  expect(Object.isFrozen(value)).toBe(true);
  if (value && typeof value === 'object') {
    for (const nested of Object.values(value)) {
      if (nested && typeof nested === 'object') {
        expectDeepFrozen(nested);
      }
    }
  }
}

describe('overview preferences persistence', () => {
  it('creates fresh recursively frozen defaults with the public constants', () => {
    const first = createDefaultOverviewPreferences();
    const second = createDefaultOverviewPreferences();

    expect(OVERVIEW_PREFERENCES_VERSION).toBe(1);
    expect(OVERVIEW_PREFERENCES_STORAGE_KEY).toBe(
      'starlink.operations-overview.preferences.v1'
    );
    expect(first).toEqual({
      version: 1,
      refreshCadence: 1,
      radarEnabled: true,
      poiFilter: 'departure,arrival',
      disclosures: {
        controlsExpanded: false,
        additionalClocksExpanded: false,
        clockSettingsExpanded: false,
      },
      clocks: [
        { id: 'utc', timeZone: 'UTC', label: 'UTC (Zulu)' },
        {
          id: 'tz:America/New_York',
          timeZone: 'America/New_York',
          label: 'Washington DC',
        },
        { id: 'tz:Asia/Tokyo', timeZone: 'Asia/Tokyo', label: 'Tokyo' },
        {
          id: 'tz:America/Chicago',
          timeZone: 'America/Chicago',
          label: 'Omaha',
        },
      ],
    });
    expect(first).not.toBe(second);
    expect(first.clocks).not.toBe(second.clocks);
    expectDeepFrozen(first);
    expect(() => ((first.clocks as unknown[])[0] = null)).toThrow();
  });

  it('roundtrips exact fields and ignores storage failures', () => {
    const storage = memoryStorage();
    const preferences = addOverviewClock(createDefaultOverviewPreferences(), {
      timeZone: 'Europe/London',
      label: ' London ',
    });

    expect(saveOverviewPreferences(storage, preferences)).toEqual({ ok: true });
    expect(JSON.parse(storage.value ?? '{}')).toEqual(preferences);
    expect(loadOverviewPreferences(storage)).toEqual(preferences);
    expect(loadOverviewPreferences(null)).toEqual(
      createDefaultOverviewPreferences()
    );
    expect(saveOverviewPreferences(undefined, preferences)).toEqual({
      ok: false,
      reason: 'storage-unavailable',
    });
  });

  it('guards malformed storage, throwing methods, nonstring returns, and versions', () => {
    const defaults = createDefaultOverviewPreferences();
    const cases: unknown[] = [
      '{',
      '[]',
      'null',
      '7',
      JSON.stringify({ version: 2, radarEnabled: false }),
      JSON.stringify({ version: '1', radarEnabled: false }),
      JSON.stringify({ constructor: { prototype: { polluted: true } } }),
    ];

    for (const item of cases) {
      expect(loadOverviewPreferences(memoryStorage(item as string))).toEqual(
        defaults
      );
    }
    expect(
      loadOverviewPreferences({
        get getItem() {
          throw new Error('lookup');
        },
        setItem() {},
      } as unknown as OverviewStorage)
    ).toEqual(defaults);
    expect(
      loadOverviewPreferences({ getItem: () => 42 as never, setItem() {} })
    ).toEqual(defaults);
    expect(
      saveOverviewPreferences(
        {
          getItem: () => null,
          setItem() {
            throw new Error('write');
          },
        },
        defaults
      )
    ).toEqual({ ok: false, reason: 'storage-failure' });
    expect(
      Object.getPrototypeOf(loadOverviewPreferences(memoryStorage('{}')))
    ).toBe(Object.prototype);
  });

  it('guards storage proxy lookup, apply, and return traps for load and save', () => {
    const defaults = createDefaultOverviewPreferences();
    const stored = JSON.stringify({ radarEnabled: false });
    const proxyStorage = new Proxy(memoryStorage(stored), {
      get(target, prop, receiver) {
        if (prop === 'getItem') {
          return new Proxy(target.getItem, {
            apply() {
              throw new Error('get apply');
            },
          });
        }
        return Reflect.get(target, prop, receiver);
      },
    });

    expect(loadOverviewPreferences(proxyStorage)).toEqual(defaults);
    expect(
      loadOverviewPreferences({
        getItem: () =>
          new Proxy(
            {},
            {
              get() {
                throw new Error('return trap');
              },
            }
          ) as never,
        setItem() {},
      })
    ).toEqual(defaults);
    expect(
      saveOverviewPreferences(
        {
          getItem: () => null,
          get setItem() {
            throw new Error('set lookup');
          },
        } as unknown as OverviewStorage,
        defaults
      )
    ).toEqual({ ok: false, reason: 'storage-failure' });
    expect(
      saveOverviewPreferences(
        {
          getItem: () => null,
          setItem: new Proxy(() => {}, {
            apply() {
              throw new Error('set apply');
            },
          }),
        },
        defaults
      )
    ).toEqual({ ok: false, reason: 'storage-failure' });
  });

  it('migrates recognized fields independently and validates options', () => {
    const loaded = loadOverviewPreferences(
      memoryStorage(
        JSON.stringify({
          radarEnabled: false,
          refreshCadence: 3,
          poiFilter: 'waypoint',
          disclosures: { controlsExpanded: true, ignored: true },
        })
      )
    );

    expect(loaded.radarEnabled).toBe(false);
    expect(loaded.refreshCadence).toBe(1);
    expect(loaded.poiFilter).toBe('waypoint');
    expect(loaded.disclosures).toEqual({
      controlsExpanded: true,
      additionalClocksExpanded: false,
      clockSettingsExpanded: false,
    });
    expect(OVERVIEW_REFRESH_OPTIONS.map((option) => option.value)).toEqual([
      1,
      2,
      5,
      10,
      30,
      'paused',
    ]);
    expect(OVERVIEW_POI_FILTER_OPTIONS.map((option) => option.value)).toEqual([
      'departure,arrival',
      '',
      'departure',
      'arrival',
      'waypoint',
      'alternate',
    ]);
  });

  it('defaults every malformed field independently without spreading pollution keys', () => {
    const loaded = loadOverviewPreferences(
      memoryStorage(
        JSON.stringify({
          version: 1,
          clocks: 'wrong',
          refreshCadence: '1',
          radarEnabled: 'false',
          poiFilter: 7,
          disclosures: {
            controlsExpanded: 'true',
            additionalClocksExpanded: true,
            clockSettingsExpanded: null,
          },
          __proto__: { polluted: true },
          prototype: { polluted: true },
          constructor: { prototype: { polluted: true } },
        })
      )
    );

    expect(loaded).toEqual({
      ...createDefaultOverviewPreferences(),
      disclosures: {
        controlsExpanded: false,
        additionalClocksExpanded: true,
        clockSettingsExpanded: false,
      },
    });
    expect(({} as { polluted?: boolean }).polluted).toBeUndefined();
  });

  it('normalizes persisted clocks with UTC first, canonical ids, limits, and duplicates', () => {
    const loaded = loadOverviewPreferences(
      memoryStorage(
        JSON.stringify({
          version: 1,
          clocks: [
            { id: 'bad', timeZone: 'America/Chicago', label: '  Omaha  ' },
            { id: 'old', timeZone: 'Etc/UTC', label: 'Wrong UTC' },
            { id: 'dup', timeZone: 'America/Chicago', label: 'Duplicate' },
            { id: 'bad-zone', timeZone: 'No/Such', label: 'Bad' },
            { id: 'empty', timeZone: 'Asia/Tokyo', label: '' },
            { id: 'lon', timeZone: 'Europe/London', label: 'London' },
            { id: 'la', timeZone: 'America/Los_Angeles', label: 'LA' },
            { id: 'den', timeZone: 'America/Denver', label: 'Denver' },
            { id: 'phx', timeZone: 'America/Phoenix', label: 'Phoenix' },
            { id: 'ak', timeZone: 'America/Anchorage', label: 'Anchorage' },
            { id: 'hon', timeZone: 'Pacific/Honolulu', label: 'Honolulu' },
            { id: 'extra', timeZone: 'Europe/Paris', label: 'Paris' },
          ],
        })
      )
    );

    expect(loaded.clocks).toHaveLength(8);
    expect(loaded.clocks[0]).toEqual({
      id: 'utc',
      timeZone: 'UTC',
      label: 'UTC (Zulu)',
    });
    expect(loaded.clocks.map((clock) => clock.id)).toEqual([
      'utc',
      'tz:America/Chicago',
      'tz:Europe/London',
      'tz:America/Los_Angeles',
      'tz:America/Denver',
      'tz:America/Phoenix',
      'tz:America/Anchorage',
      'tz:Pacific/Honolulu',
    ]);
  });

  it('enforces clock label and zone boundaries, aliases, case, and first duplicates', () => {
    const label64 = 'x'.repeat(64);
    const label65 = 'x'.repeat(65);
    const zone100 = `${'A'.repeat(92)}/Chicago`;
    const zone101 = `${'A'.repeat(93)}/Chicago`;
    const loaded = loadOverviewPreferences(
      memoryStorage(
        JSON.stringify({
          clocks: [
            { timeZone: 'utc', label: 'lower utc ignored label' },
            { timeZone: 'Etc/UTC', label: 'alias utc ignored label' },
            { timeZone: 'America/Chicago', label: 'C1' },
            { timeZone: 'america/chicago', label: 'C2' },
            { timeZone: 'Europe/London', label: 'x' },
            { timeZone: 'Europe/Paris', label: label64 },
            { timeZone: 'Asia/Tokyo', label: '' },
            { timeZone: 'Asia/Seoul', label: label65 },
            { timeZone: '', label: 'empty zone' },
            { timeZone: zone100, label: 'bad zone at max length' },
            { timeZone: zone101, label: 'too long zone' },
          ],
        })
      )
    );

    expect(loaded.clocks).toEqual([
      { id: 'utc', timeZone: 'UTC', label: 'UTC (Zulu)' },
      { id: 'tz:America/Chicago', timeZone: 'America/Chicago', label: 'C1' },
      { id: 'tz:Europe/London', timeZone: 'Europe/London', label: 'x' },
      { id: 'tz:Europe/Paris', timeZone: 'Europe/Paris', label: label64 },
    ]);
  });

  it('handles throwing Intl access and clock mutation rules without throwing', () => {
    const spy = vi
      .spyOn(Intl, 'DateTimeFormat')
      .mockImplementation(function () {
        throw new Error('intl');
      } as never);
    expect(() =>
      addOverviewClock(createDefaultOverviewPreferences(), {
        timeZone: 'Europe/London',
        label: 'London',
      })
    ).not.toThrow();
    spy.mockRestore();

    const base = createDefaultOverviewPreferences();
    expect(removeOverviewClock(base, 'utc')).toEqual(base);
    expect(relabelOverviewClock(base, 'utc', 'Zulu')).toEqual(base);
    expect(
      moveOverviewClock(base, 'tz:America/New_York', 'up').clocks[1].id
    ).toBe('tz:America/New_York');

    const added = addOverviewClock(base, {
      timeZone: 'Europe/London',
      label: 'London',
    });
    expect(added.clocks.at(-1)).toEqual({
      id: 'tz:Europe/London',
      timeZone: 'Europe/London',
      label: 'London',
    });
    expect(
      relabelOverviewClock(added, 'tz:Europe/London', ' UK ').clocks.at(-1)
    ).toMatchObject({ label: 'UK' });
    expect(removeOverviewClock(added, 'tz:Europe/London').clocks).toHaveLength(
      4
    );
    expect(
      moveOverviewClock(added, 'tz:Europe/London', 'up').clocks[3].id
    ).toBe('tz:Europe/London');
  });
});
