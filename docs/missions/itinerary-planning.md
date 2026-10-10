# Itinerary communications planning

Use **Missions → Create from itinerary** to upload a text-bearing itinerary PDF.
The application extracts UTC departures, arrivals and AR windows. Check the
mission name, revision, aircraft, call sign, airports and UTC dates before
**Confirm itinerary and create draft**. Rotated text pages are supported;
scan-only PDFs need a text-bearing replacement. PDFs are limited to 10 MiB and
parsing has a 10-second deadline. A deadline is retryable; no partial extraction
is accepted as an executable plan.

Creation makes expected leg cards, not executable legs. Select permitted X-band
satellites from configured positions and confirm that you have service access.
These defaults copy to each leg; subsequent changes affect the selected leg.
Starshield is enabled by default. Unconfirmed access or AR details remain
visible as provisional errors, and you can save an incomplete draft for later
review.

Configured global satellite records take precedence over static defaults with
that identifier. Planning requires an explicit X-band transport and a finite,
valid position; ambiguous duplicate identifiers cannot be selected. Changing a
selected satellite's position or transport requires another preview and review.
Records with an unrecognized transport band are excluded from the selector;
correct their configured band before selecting them. They cannot silently use a
static default with the same identifier.

## Review each leg

1. Open the expected leg's **Upload KML** action. Preview its KML, check any
   route timing or airport discrepancies, and explicitly acknowledge them before
   accepting. Other legs keep their own route bindings. A KML without a usable
   timing profile needs a replacement with named departure/arrival airports and
   timed primary-route endpoints.
2. Review **AR windows** first. Confirm altitude units, entry and exit UTC times
   and route occurrences. An occurrence identifies a particular traversal of a
   point, including repeated coordinates. The map shows selected spans. Correct
   an unrecognized AR section explicitly; confirm **no AR windows** when the
   checked source contains none. Excluding a row requires an explanation.
3. Review **X-band plan**. Choose an initial satellite and add manual swaps at
   timed occurrences. Lock the initial assignment or individual swaps to retain
   them during optimization. Moving or resolving a swap requires a current route
   occurrence. Manual AR Tracks remain independent overlays.
4. **Save draft**, then **Re-optimize** to compare the current or feasible
   locked baseline with the proposal. Review outage duration, longest outage and
   swaps. **Apply proposal** explicitly accepts the selected schedule. Apply,
   save and reload preserve its evaluation context and manual locks.
5. Confirm the satellite plan and Starshield setting. Acknowledge X-band outages
   and backup gaps when present, then **Save reviewed plan**. The installed leg
   is inactive. **Save reviewed plan and upload next leg** opens the next leg
   still awaiting a KML. Return to the mission to resume any saved draft.

## Interpret availability

Starshield is preferred whenever usable. Within the normal 135–225 degree
relative-azimuth conflict sector, X-band yields unless another permitted X-band
assignment avoids the conflict. AR windows use the 315–45 degree exclusion
sector. Minimum elevation is 10 degrees. Each swap degrades X-band for 15
minutes on either side of its time.

**Physical capability and operating policy** lists both states per exact UTC
interval. An X-band policy outage can coexist with physical X-band capability.
Backup guidance flags fewer than two effectively available transports among X,
Ka and Ku. Safety advice alone adds no X-band outage seconds. Keep these labels
separate when reviewing a report.

The optimizer compares candidates on a shared 60-second cadence plus exact
route, AR, outage and swap boundaries. Intervals include their start and exclude
their end. Results are optimal only within this evaluated candidate set, not
every possible continuous swap time. Generated swap buffers do not overlap; a
valid current manual schedule is also considered. Computation has a 30-second
deadline and never publishes a partial optimum after timeout.

AR heights use the confirmed source units; route interpolation supplies position
and heading between occurrences. Repeated-track runtime projection retains the
application's existing coordinate-based limitation: planning can distinguish
occurrences that runtime consumers using only coordinates cannot. Review such
routes explicitly; do not assume a finer temporal or spatial guarantee.

## Correct, resume and revise

Unsaved edits are local. **Reload saved draft** replaces them with the saved
version. If another tab saves first, the stale save returns a conflict and keeps
your entered corrections visible. Reload the current mission before retrying.
Expired previews require another upload.

**Update Route** previews a replacement for the selected leg. Existing manual
anchors and locks must be checked against the new occurrences; resolve pending
swaps and AR windows before reviewed save. Prior route sources and reviewed
history remain retained.

Use **Update itinerary** on the parent mission for a revised PDF. Confirm every
incoming-to-existing leg mapping and resolve each correction conflict before
**Apply itinerary revision**. Retained operator corrections, metadata and manual
work are reconciled with the previous source and incoming source. Retired legs
retain their history but leave the live itinerary. Lower source revisions need
explicit acknowledgment. An identical source makes no change.

Mission ZIP packages preserve planning sources and retained references.
Importing an existing mission identifier creates a new parent mission and remaps
colliding source and route identifiers throughout the package graph. Leg
identifiers remain scoped to their parent mission. Clones retain historical
reviews and inactive installed legs, but remapped dependencies can require a new
current review; open **Review leg** to preview and confirm again. Partial
itineraries keep expected numbering: reviewed legs 1 and 3 of three remain **LEG
1 OF 3** and **LEG 3 OF 3**, without an executable placeholder for leg 2. See
[package upload limits](../setup/configuration/mission-package-upload-limits.md).

A standalone route DELETE returns a conflict while any mission retains the
route, including an older unmanaged mission. Delete the owning inactive mission
to release its retained source; deleting a referenced active route cannot cancel
or damage its running simulation. Unreferenced unmanaged routes can still be
deleted independently.

## Production acceptance

From a clean, committed worktree, run:

```sh
timeout --kill-after=10s 30m tools/acceptance/itinerary-planning/run.sh
```

`--check` verifies candidate cleanliness, actor Docker access, project ownership
and port availability. The runner uses project `starlink-itinerary-planning`,
loopback port 15322, a committed archive, production Dockerfiles and Nginx. It
creates only synthetic PDFs, KMLs and API-configured satellites. Browser steps,
screenshots, API responses, console/network errors and the candidate SHA are
retained beneath
`.superpowers/sdd/2026-10-09-itinerary-xband-planning/evidence/task10`.
`ITINERARY_EVIDENCE_DIR` can select another private evidence directory.

The runner records processes, groups, commands, source paths and private volumes
before starting them. Exit, TERM and deadline handling terminate and reap owned
workers, close browsers, remove the project's containers/networks/volumes and
verify port release. Preserve evidence for review; no temporary service needs to
remain running. If interrupted by an uncatchable kill, inspect `ownership.json`
and follow
[scoped teardown verification](../development/cloud-docker.md#task-teardown-verification).
