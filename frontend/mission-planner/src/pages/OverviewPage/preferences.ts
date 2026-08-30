import {
  OVERVIEW_POI_FILTER_OPTIONS,
  type OverviewPOIFilter,
} from '../../types/monitoring';

export const OVERVIEW_PREFERENCES_VERSION = 1 as const;
export const OVERVIEW_PREFERENCES_STORAGE_KEY =
  'starlink.operations-overview.preferences.v1';
export type OverviewRefreshCadence = 1 | 2 | 5 | 10 | 30 | 'paused';
export interface OverviewClockPreference {
  readonly id: string;
  readonly timeZone: string;
  readonly label: string;
}
export interface OverviewDisclosurePreferences {
  readonly controlsExpanded: boolean;
  readonly additionalClocksExpanded: boolean;
  readonly clockSettingsExpanded: boolean;
}
export interface OverviewPreferences {
  readonly version: 1;
  readonly clocks: readonly OverviewClockPreference[];
  readonly refreshCadence: OverviewRefreshCadence;
  readonly radarEnabled: boolean;
  readonly poiFilter: OverviewPOIFilter;
  readonly disclosures: OverviewDisclosurePreferences;
}
export interface OverviewStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
export type SaveOverviewPreferencesResult =
  | { readonly ok: true }
  | {
      readonly ok: false;
      readonly reason: 'storage-unavailable' | 'storage-failure';
    };

// prettier-ignore
export const OVERVIEW_REFRESH_OPTIONS = [
  { label: '1s', value: 1 }, { label: '2s', value: 2 },
  { label: '5s', value: 5 }, { label: '10s', value: 10 },
  { label: '30s', value: 30 }, { label: 'Paused', value: 'paused' },
] as const;

const MAX_CLOCKS = 8;
const UTC_CLOCK = { id: 'utc', timeZone: 'UTC', label: 'UTC (Zulu)' } as const;
// prettier-ignore
const DEFAULT_CLOCKS = [
  UTC_CLOCK,
  { id: 'tz:America/New_York', timeZone: 'America/New_York', label: 'Washington DC' },
  { id: 'tz:Asia/Tokyo', timeZone: 'Asia/Tokyo', label: 'Tokyo' },
  { id: 'tz:America/Chicago', timeZone: 'America/Chicago', label: 'Omaha' },
] as const;

const DEFAULT_DISCLOSURES: OverviewDisclosurePreferences = {
  controlsExpanded: false,
  additionalClocksExpanded: false,
  clockSettingsExpanded: false,
};

function freezeDeep<T>(value: T): T {
  if (value && typeof value === 'object') {
    for (const nested of Object.values(value)) freezeDeep(nested);
    Object.freeze(value);
  }
  return value;
}

function copyClock(clock: OverviewClockPreference): OverviewClockPreference {
  return { id: clock.id, timeZone: clock.timeZone, label: clock.label };
}

// prettier-ignore
function preference(clocks: readonly OverviewClockPreference[], refreshCadence: OverviewRefreshCadence, radarEnabled: boolean, poiFilter: OverviewPOIFilter, disclosures: OverviewDisclosurePreferences): OverviewPreferences {
  return freezeDeep({ version: 1 as const, clocks: clocks.map(copyClock), refreshCadence, radarEnabled, poiFilter, disclosures: { controlsExpanded: disclosures.controlsExpanded, additionalClocksExpanded: disclosures.additionalClocksExpanded, clockSettingsExpanded: disclosures.clockSettingsExpanded } });
}

export function createDefaultOverviewPreferences(): OverviewPreferences {
  return preference(
    DEFAULT_CLOCKS,
    1,
    true,
    'departure,arrival',
    DEFAULT_DISCLOSURES
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isCadence(value: unknown): value is OverviewRefreshCadence {
  return OVERVIEW_REFRESH_OPTIONS.some((option) => option.value === value);
}

function isPOIFilter(value: unknown): value is OverviewPOIFilter {
  return OVERVIEW_POI_FILTER_OPTIONS.some((option) => option.value === value);
}

function readBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function readDisclosures(value: unknown): OverviewDisclosurePreferences {
  if (!isRecord(value)) return { ...DEFAULT_DISCLOSURES };
  return {
    controlsExpanded: readBoolean(value.controlsExpanded, false),
    additionalClocksExpanded: readBoolean(
      value.additionalClocksExpanded,
      false
    ),
    clockSettingsExpanded: readBoolean(value.clockSettingsExpanded, false),
  };
}

// prettier-ignore
export function validateOverviewClockInput(input: { readonly timeZone: string; readonly label: string }): OverviewClockPreference | null {
  const label = input.label.trim();
  const zone = input.timeZone.trim();
  if (label.length < 1 || label.length > 64 || zone.length < 1 || zone.length > 100) return null;
  try {
    const formatter = new Intl.DateTimeFormat('en-US', { timeZone: zone });
    const resolvedOptions = formatter.resolvedOptions;
    if (typeof resolvedOptions !== 'function') return null;
    const canonical = resolvedOptions.call(formatter).timeZone;
    if (typeof canonical !== 'string' || canonical.length < 1) return null;
    const timeZone = canonical === 'Etc/UTC' ? 'UTC' : canonical;
    return { id: timeZone === 'UTC' ? 'utc' : `tz:${timeZone}`, timeZone, label };
  } catch { return null; }
}

function normalizeClocks(value: unknown): readonly OverviewClockPreference[] {
  if (!Array.isArray(value)) {
    return DEFAULT_CLOCKS.map(copyClock);
  }
  const seen = new Set<string>(['utc']);
  const clocks: OverviewClockPreference[] = [copyClock(UTC_CLOCK)];
  for (const item of value) {
    if (clocks.length >= MAX_CLOCKS || !isRecord(item)) continue;
    const timeZone = typeof item.timeZone === 'string' ? item.timeZone : '';
    const label = typeof item.label === 'string' ? item.label : '';
    const clock = validateOverviewClockInput({ timeZone, label });
    if (!clock || seen.has(clock.id)) continue;
    seen.add(clock.id);
    clocks.push(clock);
  }
  return clocks;
}

function recognizedUnversioned(value: Record<string, unknown>): boolean {
  return (
    'clocks' in value ||
    'refreshCadence' in value ||
    'radarEnabled' in value ||
    'poiFilter' in value ||
    'disclosures' in value
  );
}

export function loadOverviewPreferences(
  storage: OverviewStorage | null | undefined
): OverviewPreferences {
  if (!storage) return createDefaultOverviewPreferences();
  try {
    const getItem = storage.getItem;
    if (typeof getItem !== 'function')
      return createDefaultOverviewPreferences();
    const raw = getItem.call(storage, OVERVIEW_PREFERENCES_STORAGE_KEY);
    if (typeof raw !== 'string') return createDefaultOverviewPreferences();
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) return createDefaultOverviewPreferences();
    if ('version' in parsed && parsed.version !== 1)
      return createDefaultOverviewPreferences();
    if (!('version' in parsed) && !recognizedUnversioned(parsed)) {
      return createDefaultOverviewPreferences();
    }
    return preference(
      normalizeClocks(parsed.clocks),
      isCadence(parsed.refreshCadence) ? parsed.refreshCadence : 1,
      typeof parsed.radarEnabled === 'boolean' ? parsed.radarEnabled : true,
      isPOIFilter(parsed.poiFilter) ? parsed.poiFilter : 'departure,arrival',
      readDisclosures(parsed.disclosures)
    );
  } catch {
    return createDefaultOverviewPreferences();
  }
}

export function saveOverviewPreferences(
  storage: OverviewStorage | null | undefined,
  preferences: OverviewPreferences
): SaveOverviewPreferencesResult {
  if (!storage) return { ok: false, reason: 'storage-unavailable' };
  try {
    const setItem = storage.setItem;
    if (typeof setItem !== 'function')
      return { ok: false, reason: 'storage-failure' };
    const payload = {
      version: 1 as const,
      clocks: preferences.clocks.map(copyClock),
      refreshCadence: preferences.refreshCadence,
      radarEnabled: preferences.radarEnabled,
      poiFilter: preferences.poiFilter,
      disclosures: {
        controlsExpanded: preferences.disclosures.controlsExpanded,
        additionalClocksExpanded:
          preferences.disclosures.additionalClocksExpanded,
        clockSettingsExpanded: preferences.disclosures.clockSettingsExpanded,
      },
    };
    setItem.call(
      storage,
      OVERVIEW_PREFERENCES_STORAGE_KEY,
      JSON.stringify(payload)
    );
    return { ok: true };
  } catch {
    return { ok: false, reason: 'storage-failure' };
  }
}

function withClocks(
  p: OverviewPreferences,
  clocks: readonly OverviewClockPreference[]
): OverviewPreferences {
  return preference(
    normalizeClocks(clocks),
    p.refreshCadence,
    p.radarEnabled,
    p.poiFilter,
    p.disclosures
  );
}

export function addOverviewClock(
  p: OverviewPreferences,
  input: { readonly timeZone: string; readonly label: string }
): OverviewPreferences {
  const clock = validateOverviewClockInput(input);
  if (
    !clock ||
    p.clocks.length >= MAX_CLOCKS ||
    p.clocks.some((c) => c.id === clock.id)
  ) {
    return withClocks(p, p.clocks);
  }
  return withClocks(p, [...p.clocks, clock]);
}

export function relabelOverviewClock(
  p: OverviewPreferences,
  id: string,
  label: string
): OverviewPreferences {
  const trimmed = label.trim();
  if (id === 'utc' || trimmed.length < 1 || trimmed.length > 64)
    return withClocks(p, p.clocks);
  return withClocks(
    p,
    p.clocks.map((clock) =>
      clock.id === id
        ? { id: clock.id, timeZone: clock.timeZone, label: trimmed }
        : clock
    )
  );
}

export function moveOverviewClock(
  p: OverviewPreferences,
  id: string,
  direction: 'up' | 'down'
): OverviewPreferences {
  const index = p.clocks.findIndex((clock) => clock.id === id);
  const target = direction === 'up' ? index - 1 : index + 1;
  if (index <= 0 || target <= 0 || target >= p.clocks.length) {
    return withClocks(p, p.clocks);
  }
  const clocks = p.clocks.map(copyClock);
  [clocks[index], clocks[target]] = [clocks[target], clocks[index]];
  return withClocks(p, clocks);
}

export function removeOverviewClock(
  p: OverviewPreferences,
  id: string
): OverviewPreferences {
  if (id === 'utc') return withClocks(p, p.clocks);
  return withClocks(
    p,
    p.clocks.filter((clock) => clock.id !== id)
  );
}
