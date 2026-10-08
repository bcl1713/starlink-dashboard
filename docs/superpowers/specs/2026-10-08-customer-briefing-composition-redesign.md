# Customer briefing composition redesign

Status: written design for customer review; implementation is not authorized
until this spec and its subsequent implementation plan are approved.

## Purpose and authority

For each leg, a customer must see when communications capability is reduced,
why, which transports remain available, and when SOF/AR restrictions apply.
Those answers must be visible within seconds on one polished operational
briefing page.

This design responds to both acceptance comments on
[PR #309](https://github.com/bcl1713/starlink-dashboard/pull/309):
[composition and semantics](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6058863586)
and
[visual design](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6059091135).
The reviewed five-leg, 290-slide deck failed customer acceptance.

The
[written-spec review](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6059411867)
adds the fully assessed primary visual checkpoint and incomplete-planning pair
defined below.

This spec supersedes the customer composition, appendix, clock display,
typography, and pagination requirements in the
[original trial design](2026-10-07-customer-mission-briefing-trial-design.md).
Its snapshot, source classification, SOF/AR, map renderer, default-off trial,
legacy isolation, and failure contracts remain applicable. Prior acceptance
reports describe the old candidate; they do not qualify the redesigned deck.

## Scope and boundaries

Rebuild the customer presentation and add separate machine-readable evidence.
Reuse immutable export snapshots, transport decisions, exact interval
partitions, resolved restrictions, route rendering, and legacy builders.
Generation remains deterministic, template-driven, offline-capable, and free of
AI authoring.

Continue in PR #309's isolated feature worktree. Keep the PR draft and the trial
default-off. No merge, rebase, legacy replacement, phase-two work, or shared
runtime changes belong to this redesign. Existing branch conflicts and missing
browser/CI qualification remain separately recorded gates.

## Customer slide contract

- A normal leg has one primary slide, containing its full-flight timeline and
  coordination table together. A six-to-eight-hour leg is not split merely
  because it contains several internal intervals.
- A dense or long leg may use a second slide. A pathological leg has a maximum
  of three customer pages. Page count follows readable customer content, never
  source-record count or a fixed number of timeline intervals.
- Five-leg representative missions target six-to-twelve slides and must have
  fewer than fifteen. Include an optional one-slide index only when useful; no
  cover, diagnostics, source appendix, or automatic detail pages.
- Never meet the budget by shrinking below the type scale, dropping a material
  window, or merging across a distinct operational condition. If readable,
  complete customer content exceeds the limit, fail the trial atomically through
  the existing legacy-ZIP fallback and persistent warning path. Preserve the
  failure reason in local acceptance evidence.

An incomplete leg uses one primary page with a concise timing/data notice and
whatever confirmed information is available. Map or endpoint failures do not
create their own slides.

## Primary page and visual system

Use a 16:9 light-background slide with a dark navy header, restrained APO gold,
minimal borders, a consistent alignment grid, and deliberate whitespace. The
reading order is leg identity/timing, overall posture, transport states, SOF/AR,
coordination windows, then optional geographic context.

The top approximately fifteen percent contains a 28–32 pt leg title, a short
optional geographic subtitle, and an 18–22 pt timing row. Use this structure:

> LEG 1 OF 5 — KADW → PAED
>
> Washington, DC → Anchorage, AK
>
> DEP 06:00 ET | ARR 13:39 ET | 7h 39m

Use resolved airport names/identifiers first, endpoint waypoint labels second,
then one leg name, then `Leg N`. If an endpoint pair cannot be resolved, use the
single fallback title instead of duplicating a route title across an arrow.
Geographic subtitles require source data; do not invent location names.

Place the APO patch consistently in the header and preserve its aspect ratio.
Starshield appears only as a transport name. Trial identification remains
visible as a small secondary label, not the main title.

The middle contains a continuous horizontal timeline with a shared ET axis:

1. Overall communications posture: at least twice a transport lane's height,
   with 18–22 pt labels and the strongest visual weight.
2. Commercial Ka, Starshield, and X-Band MILSATCOM: thinner aligned lanes with
   16–18 pt labels and neutral Up/Down/unknown styling.
3. SOF/AR: a separate thin blue/gray restriction lane.

All event boundaries align vertically. Bars remain proportional to exact UTC
duration. Only definitive posture uses green/amber/orange/red. Labels and
selective patterns preserve grayscale meaning without hatching every block.
Short windows retain their true width and get a concise callout when their
in-band label cannot fit. A brief total outage must remain identifiable.

Reserve roughly the bottom quarter to third for the customer table. The timeline
normally occupies two-thirds of the middle width; a useful map or concise
takeaways may occupy the remaining third. Reclaim that width when no map/context
is useful. These proportions guide composition; required content and font sizes
determine actual fit.

Use a compact legend on the first leg page and a small prediction footer at
10–12 pt. Do not repeat full legends, long caveats, or clock prose on every
page. Essential content never depends on the footer.

## Customer projection and table

Add a presentation view between `TrialLeg` and the PPTX builder. It owns
customer wording, compact clocks, display grouping, and page planning. It does
not mutate the canonical projection or become a second availability engine.

The full-flight graphics preserve all material state changes. Table rows
represent SOF/AR, confirmed outages, changing uncertainty, and other customer
coordination limitations. Quiet nominal periods and unchanged missing-planning
conditions do not create table rows by themselves.

Adjacent intervals may share a customer row only when their transport states,
restriction labels, operational cause, limitations, and confidence match.
Different internal source IDs alone do not prevent grouping. Preserve a mapping
to every underlying interval/source in engineering evidence. Never merge across
an intervening quiet interval, leg boundary, short complete outage, AR boundary,
or material change in uncertainty.

Use four columns: ET, Event / impact, Communications remaining, and Posture.
Native editable table cells have 14–16 pt text, a navy header, light body,
minimal gridlines, and compact posture badges. Several rows fit together; rows
do not become individual slides merely because they exist.

Customer wording names the actual impact: `Commercial Ka unavailable`,
`Starshield only`, `Takeoff SOF`, or `AR-1`. Show affected and remaining
transports and meaningful causes without hashes, source IDs, rule IDs, window
numbers, raw DTOs, or model phrases. Use concise fixed templates backed by the
captured data. Arbitrary raw source text is evidence, not slide body content.

A continuation page normally carries the remaining table rows with the same leg
identity and time context. Keep the first slide as the visual leg summary; do
not repeat each window in a table, detail card, and source page. A genuinely
long/dense timeline can use two consecutive, explicitly ranged panels only when
full-leg presentation fails readability. Every material row appears once.

## Unknown and incomplete transport planning

Preserve the canonical `?` classification and uncertain overall posture. An
unknown transport never counts as Up or Down. Fully assessed intervals retain
the existing three/two/one/zero-Up posture mapping.

For persistently incomplete X-band planning, show one primary-page note:
`X-Band planning incomplete — confirmed transport capability shown below.` Use
`?` in the X lane. The overall band remains neutral and uses confirmed
capability wording such as `Ka + Starshield confirmed` or
`Starshield confirmed`. The note makes clear that these are not definitive
three-transport posture ratings. If none is confirmed, say
`No transport confirmed available`, never `Communications unavailable` while any
transport remains unknown.

Known Ka/Starshield outages still create obvious timeline boundaries and table
rows. In those rows, name confirmed remaining transports and use a compact
`Assessment incomplete` posture qualifier. Do not repeat the
missing-prerequisite explanation in every row. If uncertainty changes within a
leg, show its actual boundaries and a customer-facing explanation where that
change matters.

SOF and AR remain coordination restrictions. They do not lower an availability
count without independent outage evidence. Show both standard fifteen-minute SOF
windows, full resolved AR periods, and overlapping transport outages.

## Human clock display

Keep exact timezone-aware instants and all three clocks in the canonical data
and engineering evidence. The customer view normally shows `HH:MM ET`, one date
in the header, and short flight duration. Use dates at midnight crossings and
EST/EDT or UTC offsets when daylight-saving ambiguity requires them.

Customer formatting never exposes microseconds. Preserve exact bar geometry; do
not round the underlying intervals. Display interval starts rounded down and
ends rounded up to minutes when fractional-minute boundaries would otherwise
understate risk. Mark such ranges as approximate with a compact legend. Show
seconds when distinct material boundaries collide at minute precision or an
operational window is shorter than one minute; round fractional seconds outward
as well. Do not inflate a narrow bar to match a rounded label.

Zulu/T-plus are secondary references at useful axis anchors or table context,
not repeated full timestamps. Each leg retains its own departure-based T-zero;
ground gaps never join flight axes. Departure changes require re-export.

## Maps and engineering artifact

Use existing rendered assets in one integrated map card per primary page when
geographic context helps. Fit the route and useful origin/destination/AR/event
markers. Keep renderer captions, internal view IDs, and diagnostic paragraphs
out of the customer deck. Additional map views are not automatic slides. Use a
useful static fallback after a map failure, or reclaim the card space; retain
renderer/fallback details in engineering evidence.

Add `exports/mission/mission-customer-briefing-evidence.json` alongside the
trial PPTX and list it in the manifest. A versioned schema records snapshot
fingerprint, ordered leg identities, exact intervals and ET/Zulu/T-plus clocks,
decisions and rule/source references, unsplit source records, restrictions,
confidence, customer-row mappings, slide assignments, and map warnings. Preserve
the existing input/source records without replacing their export files.

Evidence and PPTX come from the same immutable snapshot. Generate and validate
them atomically: trial failure adds neither partial artifact to the delivered
ZIP. Disabling the trial preserves the legacy file set. Full provenance stays
machine-readable; no technical appendix deck is added in this pass. Customer
missions and geometry remain private local evidence.

## Implementation shape and first review artifact

Keep `trial_projection.py` and exact `trial_clocks.py` as canonical inputs.
Introduce focused customer presentation/clock formatting and evidence
serialization modules. Replace the composition in `trial_pptx.py` and its layout
helpers. Update package assembly and acceptance inspections for the new atomic
artifact pair and new page contract.

The implementation plan must begin with customer-view contracts and a pair of
real editable normal-leg PPTXs, rendered to full-resolution previews:

1. Primary visual acceptance leg: Commercial Ka, Starshield, and X-Band are
   fully planned and independently classifiable throughout the flight, with no
   unknown transport states. Include nominal periods, at least one known outage,
   an overlapping outage that changes posture, takeoff/landing SOF, and
   meaningful endpoint names. Show Nominal green, Degraded amber, and Limited
   orange; include Communications unavailable red when supported by the fixture.
   Transport lanes explain the three/two/one/zero available counts, while SOF
   styling stays independent of transport state.
2. Secondary incomplete-planning leg: X-Band is intentionally unresolved.
   Demonstrate that the neutral Assessment incomplete treatment and one
   leg-level note preserve the visibility of known Ka/Starshield outages and
   confirmed remaining capability. This leg cannot substitute for the primary
   color review.

Build and render the single polished primary page first. Review its hierarchy,
posture colors, table readability, branding, and integrated map at full
resolution. Do not expand to dense/long or multi-leg implementation until that
page is explicitly accepted visually. The secondary leg verifies incomplete
planning within the same early checkpoint. This checkpoint does not replace
final production export, scan testing, or customer acceptance of the full deck.

## Verification and acceptance

Use TDD for grouping, qualified uncertainty, clock formatting, budget
enforcement, and atomic export behavior. Preserve canonical semantic tests.
Replace tests that assert old appendix/raw-content composition; trace retained
exact data through evidence instead. Validate editable native shapes/tables and
offline assets, not just text presence or bounding boxes.

Representative rendered candidates must include:

- A normal six-to-eight-hour leg: one page, readable multi-row table, both SOF
  windows, an immediately obvious outage and overlap, and remaining transports.
  All three transports are assessed for the primary visual acceptance leg; the
  separate incomplete-planning leg proves unknown X does not hide known risk.
- A dense/long leg: at most three pages, justified continuation, no duplicated
  window representation, and complete customer-relevant coverage.
- The five-leg acceptance mission: fewer than fifteen customer slides, with
  actual page counts and no embedded engineering appendix.
- Incomplete X planning, changing uncertainty, nested Ka/X outages, brief total
  outages, AR overlaps, short-flight SOF overlap, midnight/DST, and subminute
  boundaries. Unknown planning must not erase confirmed risks or imply
  certainty.
- Missing endpoint/map/timing data and over-budget content: concise notices or
  the existing safe fallback, with no silent omission or diagnostics slides.

Inspect full-resolution color and grayscale renders against the PR's design
intent: professional briefing appearance, dominant posture, quiet transport
lanes, balanced spacing, integrated map, and restrained meaningful colors.
No-overlap/font-minimum assertions alone are insufficient.

Record the customer's time to identify reduced capability, lost and remaining
transports, and SOF/AR periods from one page without explanation. The target is
seconds; measured results and explicit visual/semantic acceptance are required.
Record desktop PowerPoint version and offline title/table-cell editing.

After the early visual checkpoint, run appropriate static/unit checks and fresh
isolated exact-commit production/Nginx export, fallback, legacy comparison, and
rendered-browser acceptance. Require applicable CI on that exact head. Keep
unprovisioned-browser or missing-CI gates visible; API/render evidence cannot
stand in for them. Record ownership before launches, enforce wall limits, tear
down task-owned resources immediately after checks, and verify cleanup.

Deliver revised paired decks, separate evidence JSON, previews, slide counts,
semantic results, scan observations, and outstanding gates on draft PR #309.
Customer acceptance and a separate legacy replacement decision remain required
before any promotion or phase-two work.
