# Itinerary communications planning

This guide describes current `dev`. Automatic itinerary creation/revisions and
route SIGMET attention/live crossing timing were added after v1.0.0; see
[release notes](../release-notes.md).

Choose **Create from itinerary** on Missions, select the text-bearing PDF and
all route KMLs, then choose **Generate mission**. The server extracts the legs,
associates routes and AR windows, and generates an X-band plan using the
configured satellite list. A completed import opens the ordinary mission page;
legs remain inactive until explicitly activated. There is no separate access
confirmation, proposal application or publication workflow.

KML timestamps retain seconds. PDF times are matched at minute precision with
one minute of tolerance. Larger differences can still match when route
endpoints, dates and occurrence evidence identify one assignment. AR entry is
derived from the PDF's takeoff-to-entry offset; AR exit uses its exit-to-landing
offset on the KML timeline. Ambiguous route or AR associations appear as
targeted corrections. Missing or contradictory evidence is not silently replaced
with guessed values.

Use the normal leg editor to adjust takeoff, edit transports or update a route.
Updating an active route requires deactivation. A route-bound AR or handover
must be uniquely associated with the new geometry before replacement can
complete.

Choose **Update from itinerary** on an imported mission, supply a new PDF, KMLs,
or both, and select **Update mission**. Omitted sources are reused where valid.
Changes apply automatically without a JSON review or extra approval. The mission
keeps its name and ID, compatible manual edits survive, and uploaded changes
take precedence on conflicting fields. Prior revisions and source documents
remain in the mission package. Legs appear in chronological departure order in
the mission and exported briefing.

Imports continue on the server when the dialog closes. Reopening it in the same
browser resumes the saved operation. Upload limits are 10 MiB for the PDF and 16
KMLs totaling 40 MiB. Operations have a 20-minute overall deadline and bounded
worker execution. Existing itinerary missions are converted on server startup,
preserving accepted legs and unfinished source records for revision recovery.

## Transport availability

Set X-band, Ka and Starshield defaults in **Transport availability** on the
mission page. Legs inherit these settings unless their leg editor selects an
explicit override. Choose **Inherit mission** to return a leg to the defaults.
Save availability regenerates affected profiles, coverage, fallback and call
continuity. New legs inherit the current mission defaults. Starshield remains
available unless explicitly disabled or marked unavailable.

An equipment failure recorded in Operator applies from that time through the
rest of the mission, including later legs, until restored. Restore returns to
the planned defaults and overrides; it does not enable a deliberately disabled
transport. Simulation failures belong to that replay run and do not change live
planning. Availability history and earlier mission evidence remain retained.

Unavailable transports keep their configured points, but their map cues,
upcoming actions and traffic links become inactive. Restoration reactivates
relevant future cues without replaying expired alerts. Unknown Starshield
location or handover timing alone does not mean an outage. Transition windows
remain map advisories; planning treats the full window as an outage only when
Starshield is the sole usable transport. Usable Ka or coordinated X fallback
protects the plan.

Outputs are best estimates. Saving does not require uncertainty, predicted
outage or backup-gap acknowledgments. Invalid or missing route/configuration
inputs still need correction. If a save is not confirmed, keep your edits,
refresh the confirmed state and retry after checking concurrent changes.

## Packages and retained sources

Mission ZIP packages preserve planning sources and revision history. Importing a
package with a colliding mission identifier creates a new parent mission and
remaps retained source and route references. Imported legs remain inactive.
Inspect import warnings and activate the required leg explicitly. See
[package import](mission-package-import.md) and
[export preparation](planning/outputs.md).

## Acceptance evidence

The itinerary acceptance runner at `tools/acceptance/itinerary-planning/run.sh`
originated with the earlier staged review workflow. Treat its stored screenshots
and reports as historical evidence; the current create/update controls and
ordinary editable mission workflow above are authoritative. Follow the
[development workflow](../development/workflow.md) for current validation and
resource cleanup.
