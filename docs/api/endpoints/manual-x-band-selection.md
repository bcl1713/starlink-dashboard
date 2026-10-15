# Manual X-band satellite selection

Configuration → Network Traffic offers a **Planned X-band satellite** selector.
Choose a configured X-band satellite or **None**. Selection is planning data; it
does not command radio hardware or establish measured connectivity.

## Ownership and persistence

The backend saves the manual satellite ID in
`data/settings/x-band-selection.json`, using an atomic file replacement. The
settings volume must persist this directory across container recreation. The
default is no selection. Reloads and backend restarts retain a saved choice.

An active mission leg owns satellite selection, including automatic handoffs.
Manual saves are rejected while any mission leg is active, even if its route or
satellite is unavailable. Deactivating the mission restores the previous manual
choice if it is still a configured X-band satellite. A mission with no selected
satellite does not fall back to the manual choice.

Removing, renaming, or changing the transport of a saved satellite leaves no
effective manual selection and displays a warning in Configuration. The saved ID
remains available for diagnosis until the operator replaces or clears it. An
empty satellite configuration disables the selector; an invalid saved choice can
still be cleared.

## GET `/api/active-x-link`

The existing active-link response remains the shared selection authority for
Overview, its planned-satellite card, its configured link and map diagnostics.
It now also returns:

| Field                          | Meaning                                                                                                                    |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `selection_source`             | `mission`, `manual`, or `none`; mission ownership persists even without a selected satellite.                              |
| `manual_satellite_id`          | Saved manual ID, or `null`; mission activation does not overwrite it.                                                      |
| `manual_selection_invalid`     | Whether the saved ID is no longer configured for X-band.                                                                   |
| `manual_selection_unavailable` | Present and `true` when dormant manual settings cannot be read during an active mission; mission selection remains usable. |

A valid manual selection returns `satellite_id` even without aircraft telemetry.
In that case, link geometry is empty and the unfiltered rule state is `null`.
`normal` and `warning` describe the configured forbidden-azimuth rule, not
measured connectivity. Existing optional `state` filtering is preserved.

Overview refreshes selection once per second, including background windows, so
successful saves appear without a reload. Configuration refreshes satellite
configuration every five seconds. Same-window saves publish the confirmed
selection to the shared query cache and refresh authoritative state.

## PUT `/api/active-x-link/selection`

Save a manual choice:

```json
{ "satellite_id": "X-1" }
```

Clear the saved choice:

```json
{ "satellite_id": null }
```

The field is required. Other fields, non-string IDs, blank IDs, nonexistent
satellites and satellites with another transport are rejected. Satellite IDs
match configured names exactly. Success returns the complete confirmed
active-link response.

| Status | Meaning                                                                                |
| ------ | -------------------------------------------------------------------------------------- |
| `200`  | Choice persisted; confirmed selection returned.                                        |
| `409`  | An active mission controls selection; manual choice unchanged.                         |
| `422`  | Invalid payload or satellite; manual choice unchanged.                                 |
| `503`  | Storage or initialization unavailable; failed persistence retains the previous choice. |

The UI reports an unconfirmed save and refreshes selection after request errors:
a network failure can lose the response to an otherwise successful write.

The mission lifecycle lock serializes selection reads and writes with mission
activation/deactivation. Storage failures do not silently reset or overwrite
unreadable settings.

## Verification

Backend contracts cover switching, clearing, persistence, unavailable telemetry,
mission priority/restoration, invalid configuration, strict payloads and atomic
save failures. Frontend contracts cover the selector and Overview consumer,
disabled/error states and retry.

Run production browser acceptance against a fresh isolated Compose project using
the production Dockerfiles, Nginx proxy and persistent settings volume:

```sh
cd frontend/mission-planner
OVERVIEW_ACCEPTANCE_BASE_URL=http://127.0.0.1:15281 \
  ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD) \
  npx playwright test --config playwright.manual-x-acceptance.config.ts
```

The test uses real APIs and inspects rendered Three link resources. It verifies
an already-open Overview, reload persistence, mission override/restoration,
removed selections and clearing. It leaves `X-281-A` selected so the runner can
also restart the isolated backend and confirm persistence through the Nginx API.
Only run this test on a task-owned acceptance project: it creates satellites and
a mission in that project's storage.
