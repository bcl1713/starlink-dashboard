import type {
  AdsbContact,
  AdsbSettings,
  AdsbSourceStatus,
  AdsbTrafficBundle,
} from '@/services/overview-adsb';
export interface AdsbContactView extends AdsbContact {
  included: boolean;
  selection?: 'included' | 'excluded' | 'background' | 'not_selected';
  freshness: 'current' | 'stale';
  position_age_seconds: number;
  label: string;
}
export interface AdsbSnapshot {
  contacts: AdsbContact[];
  sources: AdsbSourceStatus[];
  generatedAt: number;
}
export function emptyAdsbSnapshot(): AdsbSnapshot {
  return { contacts: [], sources: [], generatedAt: -Infinity };
}
export function projectAdsbContacts(
  contacts: readonly AdsbContact[],
  settings: AdsbSettings,
  nowMs: number
): AdsbContactView[] {
  if (!settings.enabled) return [];
  const newest = new Map<string, AdsbContact>();
  for (const c of contacts) {
    const old = newest.get(c.hex);
    if (
      !old ||
      c.position_observed_at_ms > old.position_observed_at_ms ||
      (c.position_observed_at_ms === old.position_observed_at_ms &&
        c.acquired_at_ms > old.acquired_at_ms)
    )
      newest.set(c.hex, c);
  }
  const included = new Set(settings.include_hexes),
    excluded = new Set(settings.exclude_hexes);
  return [...newest.values()]
    .sort((a, b) => a.hex.localeCompare(b.hex))
    .flatMap((c) => {
      const age = nowMs - c.position_observed_at_ms;
      if (
        age < 0 ||
        age >= 120000 ||
        !Number.isFinite(age) ||
        excluded.has(c.hex)
      )
        return [];
      const explicit = included.has(c.hex);
      const callsign = (c.callsign ?? '').trim().toUpperCase();
      if (
        !explicit &&
        (settings.mode === 'included_only' ||
          c.military !== true ||
          (settings.callsign_substrings.length > 0 &&
            !settings.callsign_substrings.some((part) =>
              callsign.includes(part)
            )))
      )
        return [];
      return [
        {
          ...c,
          included: explicit,
          freshness: age < 30000 ? ('current' as const) : ('stale' as const),
          position_age_seconds: age / 1000,
          label: c.callsign?.trim() || c.registration?.trim() || c.hex,
        },
      ];
    });
}
export function acceptAdsbBundle(
  previous: AdsbSnapshot,
  settings: AdsbSettings,
  bundle?: AdsbTrafficBundle
): AdsbSnapshot {
  if (!settings.enabled) return emptyAdsbSnapshot();
  const excluded = new Set(settings.exclude_hexes);
  const retained = previous.contacts.filter((c) => !excluded.has(c.hex));
  const eligibleKeys = new Set(
    settings.include_hexes
      .filter((h) => !excluded.has(h))
      .map((h) => `hex:${h}`)
  );
  if (settings.mode === 'military_and_included') eligibleKeys.add('military');
  const current =
    retained.length === previous.contacts.length &&
    previous.sources.every((s) => eligibleKeys.has(s.key))
      ? previous
      : {
          ...previous,
          contacts: retained,
          sources: previous.sources.filter((s) => eligibleKeys.has(s.key)),
        };
  if (
    !bundle ||
    bundle.settings_revision !== settings.revision ||
    bundle.generated_at_ms < current.generatedAt
  )
    return current;
  const old = new Map(current.contacts.map((c) => [c.hex, c]));
  const contacts = bundle.contacts
    .filter((c) => !excluded.has(c.hex))
    .map((c) => {
      const prior = old.get(c.hex);
      return prior &&
        (prior.position_observed_at_ms > c.position_observed_at_ms ||
          (prior.position_observed_at_ms === c.position_observed_at_ms &&
            prior.acquired_at_ms > c.acquired_at_ms))
        ? prior
        : c;
    });
  return {
    contacts,
    sources: bundle.sources.filter((s) => eligibleKeys.has(s.key)),
    generatedAt: bundle.generated_at_ms,
  };
}

// Management keeps every fresh catalog contact; Overview eligibility only
// determines the status badge, never which aircraft can be searched.
export function projectAdsbCatalog(
  contacts: readonly AdsbContact[],
  settings: AdsbSettings,
  nowMs: number
): AdsbContactView[] {
  const selected = new Set(
    projectAdsbContacts(contacts, settings, nowMs).map((c) => c.hex)
  );
  const included = new Set(settings.include_hexes);
  const excluded = new Set(settings.exclude_hexes);
  return projectAdsbContacts(
    contacts,
    {
      ...settings,
      include_hexes: contacts.map((c) => c.hex),
      exclude_hexes: [],
      mode: 'military_and_included',
      callsign_substrings: [],
    },
    nowMs
  ).map((c) => ({
    ...c,
    included: included.has(c.hex),
    selection: excluded.has(c.hex)
      ? 'excluded'
      : included.has(c.hex)
        ? 'included'
        : selected.has(c.hex)
          ? 'background'
          : 'not_selected',
  }));
}
