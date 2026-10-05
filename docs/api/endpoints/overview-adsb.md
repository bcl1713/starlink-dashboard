# Overview ADS-B aircraft

Shared settings and an ephemeral global aircraft cache. All timestamps are UTC
epoch milliseconds. The feature defaults off and is independent of missions,
telemetry, measured links and camera state.

## Settings

`GET /api/overview-adsb/settings` returns the complete confirmed configuration:

```json
{
  "enabled": false,
  "mode": "military_and_included",
  "include_hexes": [],
  "exclude_hexes": [],
  "callsign_substrings": [],
  "revision": 0
}
```

`PUT /api/overview-adsb/settings` accepts a nonempty partial update:

```json
{ "enabled": true, "include_hexes": ["00ab12", "000001"] }
```

It returns all confirmed fields with an incremented revision. Hex entries must
be exactly six hexadecimal digits; leading zeroes are preserved, entries are
trimmed, uppercased and deduplicated. Callsign substrings are also trimmed,
uppercased and deduplicated. Unknown fields, invalid entries or types and an
empty update return 422. Corrupt/unavailable settings and failed durable writes
return 503. Updates preserve unspecified fields under a lock and atomic rename.
Settings persist in `data/settings/overview-adsb.json` across restart.

Modes are `military_and_included` and `included_only`. Exclusion always wins,
including entries saved in both lists. Explicit inclusion admits civilian or
unknown military classifications and bypasses the background callsign filter.
Otherwise the contact must be military, military mode must be selected and at
least one callsign substring must match. An empty substring list admits all
military contacts. Included-only mode with no included hexes produces no
traffic.

## Traffic

`GET /api/overview-adsb/traffic` reads the shared cache without upstream calls:

```json
{
  "settings_revision": 1,
  "generated_at_ms": 1791028800000,
  "contacts": [
    {
      "hex": "00AB12",
      "callsign": "RCH123",
      "registration": "N123",
      "aircraft_type": "C17",
      "military": true,
      "latitude": 38,
      "longitude": -90,
      "altitude": { "value": 30000, "unit": "ft", "source": "barometric" },
      "ground_speed_knots": 450,
      "track_degrees": 90,
      "position_observed_at_ms": 1791028800000,
      "acquired_at_ms": 1791028800000
    }
  ],
  "sources": [
    {
      "key": "military",
      "last_success_at_ms": 1791028800000,
      "error": null,
      "retry_at_ms": null
    }
  ]
}
```

Optional identity, military, altitude, speed and track fields can be null.
Altitude source is `barometric` or `geometric`, with feet explicitly reported.
Track describes ground movement, not heading. Surface marker placement does not
invent an altitude measurement. Missing fields remain unavailable.

Source keys are `military` and `hex:HHHHHH`. Provider failures return 200 with
per-source sanitized status and retained unexpired contacts; settings failure
returns 503. Disabled returns empty contacts/sources. Restart preserves settings
but starts with no live contacts or source cache.

The application owns one 15-second acquisition cycle, with at most four
individual requests at once. Current included contacts supplied by the current
military response avoid an individual request; others use the hex endpoint.
Per-source failures back off 15/30/60/120/240/300 seconds, respecting a longer
Retry-After. Unexpired retry deadlines survive disable/re-enable, mode changes
and removing/reintroducing a source. Sources recover independently. Browser
reads never multiply these acquisitions.

Position observation time is provider response `now` minus `seen_pos`, using
`lastPosition`'s own age when appropriate. Message/receiver age is not
substituted. Observation age below 30 seconds is Current; 30 through less than
120 seconds is Stale; at 120 seconds the position expires. Cached/repeated
replies, failed requests and older duplicates never renew observation time.
Saved lists survive contact expiry.

Visible clients poll confirmed settings and enabled traffic every five seconds
and refresh on focus/foreground. Hidden clients resume on return. Clients retain
the highest confirmed revision, project matching traffic against that revision,
and expire retained positions locally even if requests fail.

Aircraft data: [adsb.lol](https://adsb.lol/),
[ODbL license](https://opendatacommons.org/licenses/odbl/1-0/). Provider schema:
[adsb.lol API](https://api.adsb.lol/api/openapi.json) and
[readsb JSON](https://github.com/wiedehopf/readsb/blob/dev/README-json.md).
Before enabling broadly, review provider usage expectations and attribution;
this implementation does not authorize operational rollout.
