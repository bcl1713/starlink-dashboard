# Overview ADS-B aircraft layer addon design

## Status and authority

Approved by the user on 2026-10-03 after review of the written spec. This addon
is a documentation-only addition on `feat/starshield-flow-line-arc`. Approval
authorizes committing this document on that branch; implementation planning and
product code require a subsequent request.

This is an independent addon to the
[Overview design](2026-09-30-responsive-overview-design.md), compatible with the
[traffic arc and link controls](2026-10-03-overview-traffic-paths-design.md).
It does not expand that effort's delivery scope or depend on the
[deferred orbital experiment](2026-10-03-orbital-traffic-experiment-design.md).

## Intent and success criteria

Operators want to monitor aircraft they have identified as traveling to the
same places as their own aircraft. They also want to watch military traffic,
build an include list from that traffic, and then optionally display only that
list. Identification is manual; the feature does not infer destinations or
discover aircraft based on mission similarity.

The normal installation has a Configuration window operated by a driver and an
Overview window on a separate monitor for viewers. Configuration owns editing;
Overview stays primarily a display, with aircraft details available on click.
The map is usually viewed at a broad geographic scale, so worldwide coverage
must not be replaced by a 250-nautical-mile search around the own aircraft.

Success means both windows use the same saved settings and traffic selection,
explicitly included aircraft remain tracked globally, and operators can exclude
their current aircraft to avoid a second marker alongside the existing telemetry
marker. The addon preserves route, camera intent, telemetry, metrics, history,
communications links, configured satellites, and existing warnings.

## First-version scope

- An optional ADS-B aircraft layer, disabled by default.
- Two modes: **Military + included** and **Included only**.
- Exact ICAO hex include and exclude lists, with exclusions always winning.
- Multiple case-insensitive callsign substrings for background military traffic.
- Current observed positions, persistent labels for included aircraft, and
  read-only details on click.
- A Configuration aircraft table and saved-list editors.
- Shared settings that survive browser reloads, service restarts, and mission
  changes; updates reach the other window without a reload.
- Brief retention of lost contacts with a stale indicator before removal.

General civilian traffic, country or operator-country filters, flight trails,
destination matching, alerts, and automatically following ADS-B contacts are
outside this version. A civilian aircraft is shown only through explicit hex
inclusion. There is no initial `All aircraft` or `Exclude military` mode.

## Display modes and filter precedence

Selection is installation-wide and independent of map zoom, camera position,
the current route, and the own aircraft's location.

| Mode | Background traffic | Explicitly included aircraft |
| --- | --- | --- |
| Military + included | Provider-classified military aircraft passing the callsign filter | Globally tracked military or civilian aircraft |
| Included only | None | Globally tracked military or civilian aircraft |

For an enabled layer, apply the following rules in order:

1. An excluded hex is hidden, even if it is also included.
2. An included hex is eligible regardless of military classification or
   callsign. Inclusion does not bypass position validity or expiry.
3. In `Included only` mode, every remaining contact is hidden.
4. In `Military + included` mode, remaining contacts must be classified as
   military and pass the callsign filter.

An empty callsign list accepts all background military traffic. Otherwise, at
least one substring must occur anywhere in the normalized callsign. For example,
`RCH` and `REACH` accept either match; they do not require both. `RCH12` also
matches `RCH123`. Missing callsigns do not pass a nonempty filter. There are no
regex, wildcard, exact-match, prefix-mode, or negative-callsign operators.

Trim callsigns and filter entries and compare without case sensitivity. Ignore
blank filter entries and deduplicate equivalent entries. Require exactly six
hexadecimal digits for saved ICAO hex entries, normalize their case, preserve
leading zeroes, and reject invalid entries with visible validation feedback.
Non-ICAO identifiers are not accepted as substitutes for ICAO hex codes.

Deduplicate contacts by normalized hex across military and explicit lookups.
Changing modes preserves both saved lists and the callsign filter. `Included
only` with an empty include list is a valid empty view. If a hex appears in both
lists, preserve the explicit conflict, explain it in Configuration, and hide
that contact until the exclusion is removed.

## Configuration and shared settings

Add an ADS-B section to `ConfigurationPage.tsx` using existing form and save
feedback conventions. Proposed persisted fields are:

| Field | Default | Purpose |
| --- | --- | --- |
| `enabled` | `false` | Show the optional layer |
| `mode` | `military_and_included` | Either discovery mode or `included_only` |
| `include_hexes` | Empty list | Explicit global tracking and labels |
| `exclude_hexes` | Empty list | Unconditional suppression |
| `callsign_substrings` | Empty list | Narrow background military contacts |

Use a dedicated backend-owned settings store following the existing atomic
persisted-settings pattern in `app/services/overview_link_settings.py`. These
are shared installation settings, not mission state or local-storage
preferences. Save only supplied fields, preserve unrelated settings, validate
before persistence, and return the complete confirmed settings with a revision.
Save failures retain the last confirmed settings and show an error in
Configuration. Initial loading or unavailable settings keep the ADS-B layer off
until a confirmed configuration is available.

The Configuration table lists all eligible, unexpired contacts in the active
Overview layer, including contacts outside the camera's current visible area or
behind the globe. It is not a separate unfiltered discovery feed. Use a stable
hex identity, callsign or fallback identity, inclusion status, and freshness in
each row. Provide **Include** and **Exclude** actions here, not in Overview.
Inclusion saves the hex rather than the current callsign; subsequent callsign
changes do not remove that aircraft from the include list.

Exclusion removes a contact from the active table and map once the setting is
confirmed. Separate saved-list editors keep excluded and currently unavailable
included aircraft manageable, with actions to remove entries. Removing an
include entry can leave that aircraft visible as background military traffic;
it does not imply exclusion. When the layer is disabled, the active table is
empty and the saved-list editors remain available.

Both windows must read confirmed backend state. Poll settings at most five
seconds apart while visible, and refresh on returning to the foreground.
A Configuration save updates its own view immediately after confirmation;
the Overview window applies it within the next settings poll. Browser-local
query invalidation alone is insufficient for separate windows. Traffic bundles
carry the settings revision; an older in-flight response cannot restore contacts
hidden by a newer exclusion, mode change, or disable action.

## Provider and data ownership

Use adsb.lol as the initial provider. Its
[public API reference](https://api.adsb.lol/docs) and
[published schema](https://api.adsb.lol/api/openapi.json) document `/v2/mil` for
military contacts and `/v2/hex/{icao_hex}` for specific aircraft. The geographic
endpoints are capped at 250 nautical miles and are not needed for this scope.
The API currently says use is free, notes a possible future feeder API key,
asks production users to contact the maintainer, and identifies ODbL licensing.
Include provider attribution and a license link in the ADS-B Configuration
section. Verify current usage requirements before eventual production rollout;
this documentation task does not contact the maintainer.

One backend service owns upstream acquisition, the normalized contact cache,
filtering, and freshness. Both browser windows consume that shared result rather
than fetching adsb.lol independently. Provider classification supplies military
eligibility; do not infer it from a callsign substring.

In `Military + included` mode, acquire the global military feed and look up
included hexes not already supplied with a current position. In `Included only`
mode, stop military-feed acquisition and look up only included hexes. Do not
look up excluded entries. Use documented single-hex queries; do not assume bulk
lookup syntax without verifying provider support during later implementation.

Target a 15-second refresh cycle, coalesce simultaneous browser requests, and
do not overlap upstream cycles or multiply them by viewer count. Respect
provider retry delays and use backoff for failures rather than immediate retry
loops. The 15-second interval is a display target, not an upstream service
guarantee. Disabled settings stop ADS-B acquisition and remove its rendering
resources. Persist settings, but do not restore live contact positions from disk
after a service restart.

Normalize each contact to its hex, optional callsign, registration, aircraft type,
military classification, position, optional altitude, ground speed and track,
position observation time, and acquisition time. Use the newest valid observed
position for a duplicate; an older response cannot overwrite it. Missing
optional details stay unavailable. ADS-B data never enters own-aircraft
telemetry, route timing, communications metrics, or operational warning rules.

## Freshness and unavailable data

The defaults agreed during the interview are:

| Position age | Presentation |
| --- | --- |
| Less than 30 seconds | Current contact |
| At least 30 seconds but less than 120 seconds | Last observed position with a stale indicator |
| At least 120 seconds | Removed from the active layer and table |

Age refers to the position observation, not the latest browser poll or HTTP
success. The [readsb format reference](https://github.com/wiedehopf/readsb/blob/dev/README-json.md)
defines `seen_pos` as seconds before the response timestamp and its v2 response
timestamp as epoch milliseconds. Normalize those units in the adapter and
derive position time as `now - seen_pos * 1000`. A provider `lastPosition` can
supply a retained position using its own age. Message-only updates and repeated
cached responses cannot reset position age.

Require valid finite latitude and longitude within their legal ranges and a
usable observation timestamp. Reject nonfinite or negative position ages and
observation times in the future. Missing age or invalid position cannot create a
new marker. If a later record lacks a position, retain the previously valid
position only until its original expiry. Do not substitute receiver estimates,
invent coordinates, or extrapolate movement during gaps. Missing altitude does
not suppress a valid geographic contact; use the existing globe's marker
clearance without claiming an altitude measurement.

Provider failures retain existing contacts only for their remaining lifetime.
Advance stale and expiry transitions locally even when traffic requests fail.
A failed military request does not invalidate a successful explicit lookup, or
vice versa. Configuration reports source errors and last successful acquisition;
the map communicates individual stale contacts without a new global warning
banner. A fresh returning contact reappears, and an included aircraft's saved
entry is never deleted merely because it expires from the map.

## Overview presentation and interaction

Render ADS-B contacts through the existing React Three Fiber globe projection.
Use a distinguishable aircraft marker style subordinate to the own-aircraft
marker and route. Show observed track orientation when available; do not label
track as heading. Preserve normal Earth occlusion and surface clearance.

Every included contact has a persistent callsign label whenever its marker is
visible. Fall back to registration, then hex if the callsign is absent. Other
contacts have no permanent labels. Keep included labels readable at 1920×1080,
allow positioning to reduce overlap, and do not replace included labels with an
aggregate count. Stale markers use a subdued style plus a stale symbol or text,
so freshness is not communicated by color alone; included labels remain present.

Clicking any visible ADS-B aircraft opens a read-only detail panel showing hex,
callsign, registration, aircraft type, military status, available altitude with
units and source, ground speed, track, and position age/current-or-stale status.
Unavailable fields are explicit. The panel has a close control and supports
Escape and accessible focus handling. It provides no include/exclude editing.
It updates with its selected contact; removal, exclusion, or disabling the layer
closes it. Selection never changes camera framing or replaces the own-aircraft
follow target. A camera drag must not accidentally select an aircraft.

Add an ADS-B legend entry only when contacts are rendered. Keep data-layer
selection global while allowing normal camera and globe occlusion to determine
which markers are visually visible. Reuse batched or instanced marker rendering
where suitable; do not add a DOM label for each background military aircraft or
recalculate the entire dataset every animation frame. Avoid silently truncating
eligible traffic; demonstrate acceptable behavior against representative global
military datasets during later implementation.

## Architecture choice

The selected approach uses one backend acquisition and filtering service with
separate frontend presentation and Configuration editing. It follows the
repository's persistent-settings conventions and gives both windows the same
traffic and revision semantics.

Direct per-browser provider access would duplicate requests and complicate
shared freshness and settings. Worldwide civilian collection would add data
acquisition and rendering work outside the agreed need. Neither alternative is
part of the first version. Keep the addon modular instead of embedding provider
logic and list editing in the already substantial `OverviewPage.tsx`.

## Acceptance criteria for a later implementation

1. New settings default to an off layer and `Military + included` mode. Enabling
   that mode shows worldwide provider-classified military contacts without a route,
   viewport, or 250-nautical-mile restriction.
2. Inclusion admits a civilian contact and bypasses callsign filtering. Exclusion
   suppresses both included and background contacts, including overlapping list
   entries. Each hex produces at most one ADS-B marker.
3. Callsign substrings match anywhere, ignore case and padding, and combine with
   OR. Empty filters admit all military background contacts; missing callsigns
   fail a nonempty filter. Similar civilian callsigns alone never qualify.
4. `Included only` hides every nonincluded aircraft and stops military-feed
   acquisition. Empty lists produce an empty view. Mode changes preserve lists
   and filters, and do not reset the camera.
5. Configuration inclusion immediately adds permanent labeling to an existing
   contact after save confirmation. Exclusion removes it; removing inclusion
   alone leaves an otherwise eligible military contact visible without a label.
   Saved entries remain editable when their contacts are unavailable or excluded.
6. Included labels have identity fallbacks. Every ADS-B marker opens read-only details;
   controls do not interfere with camera drags, focus, Escape, or existing map
   controls. Stale indicators remain readable at 1080p.
7. Two separate browser windows converge on saved changes within one five-second
   polling interval plus API response time while visible and the service is
   available, without reload. Settings survive browser and service restarts
   and mission changes. Save failures and stale responses preserve confirmed
   state and cannot resurrect excluded traffic.
8. Position ages immediately below, at, and above 30 and 120 seconds behave as
   specified. Cached responses, missing positions, message-only updates, malformed
   ages, failed requests, and duplicate older positions cannot extend freshness.
   Expired included contacts reappear when fresh without list editing.
9. Upstream work is shared across windows, disabled mode does no acquisition,
   requests do not overlap refresh cycles, and provider failures respect backoff.
   Turning the layer off releases markers, labels, selection, timers, and buffers.
10. Representative worldwide military traffic remains usable alongside existing
    globe layers. Route/history, metrics, links, telemetry marker, camera intent,
    and warning behavior retain their existing contracts. Verification uses
    controlled provider fixtures and browser checks rather than depending on live
    traffic availability.

This document defines the addon contract. It is not an executable implementation
plan and does not authorize product changes.
