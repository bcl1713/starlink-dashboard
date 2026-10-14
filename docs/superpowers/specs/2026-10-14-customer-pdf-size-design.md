# Customer PDF rendering and asset reuse

Status: approved by the user on 2026-10-14. Approval covers the design and
preparation of its implementation plan. This specification covers issue
[327](https://github.com/bcl1713/starlink-dashboard/issues/327). Implementation
will use a separate branch from `origin/dev`; PR323 has merged into that branch
at `e766a595b313d7766959af61cf394b97bc397f21`.

## Outcome and scope

Generate substantially smaller customer PDFs by correcting timeline drawing,
deduplicating assets during PDF assembly, and sizing maps and the APO logo for
their actual printed dimensions. Customers retain the current readable layout,
searchable text, route information, and warning semantics. Operators continue to
receive the production-generated PDF inside Export Mission ZIP without a manual
recompression step.

The user's direction on 2026-10-14 supersedes the issue's proposed byte caps.
About 5 MB is a rough expectation for the retained five-page example, not a hard
acceptance target or a delivery guarantee. There is no 1 MB preferred cap. File
size alone must not reject a valid briefing, omit content, trigger a warning, or
force additional quality reduction. Success requires fixing the causes and
demonstrating the resulting size and visual quality on representative exports.

This change covers four parts of the existing PDF pipeline. ZIP compression,
evidence schema/storage redesign, itinerary planning, and export UI changes are
outside its scope. Required audit evidence and package contracts remain intact.

## Baseline and findings

The private production export recorded in issue327 has five pages and contains
39,081,819 bytes. Its image streams account for 99.20% of the file. Three copies
of the header logo account for 25,480,011 bytes; repeated timeline backgrounds
account for 9,436,140 bytes; one primary map accounts for 3,759,443 bytes.

The current `APO Patch.jpg` file contains PNG data, with 2048 by 2048 RGB
pixels. Chromium embeds it as an 8,493,337-byte lossless image. Its CSS size is
84 by 84 pixels, or 63 by 63 PDF points. Changing the filename or declared MIME
type alone does not solve the excessive raster resolution.

The timeline uses an SVG pattern for each transport interval whose state is
`Down`. A controlled browser reproduction with the current document and CSS
produced one identical 922 by 185 background raster and one bottom strip per
pattern placement. Twenty intervals across three lanes produced 60 copies,
adding 3,176,160 image-stream bytes. Replacing only the pattern fills in a
diagnostic copy removed those images; removing the logo's circular clip did not.

`assemble_customer_pdf` appends independently cached leg PDFs without asset
deduplication. Three synthetic leg fragments assembled to 35,240,295 bytes.
Repeated lossless deduplication reduced that example to 8,616,736 bytes with
identical text, page dimensions, and every rendered RGB pixel at 72 and 300 DPI.
A single pypdf deduplication pass left the three logos separate because their
image dictionaries initially referenced different, identical color profiles.
Deduplication must account for these dependency relationships.

Maps currently use a 1920-pixel width and a height derived from the measured
card's aspect ratio. The reported map occupied 210 by 202.5 PDF points, yielding
about 658 pixels per printed inch. This is excessive for its placement.

The controlled reproductions establish the causes; they do not replace the
private production fixture or qualify a future implementation for acceptance.

## Selected approach

Correct image production and timeline primitives in the background renderer,
then deduplicate reusable PDF objects during final cached-leg assembly. Keep the
current preparation/cache architecture and the browser-free ready export path.
This combines savings within each fragment with savings across fragments.

Deduplication alone retains an oversized logo and oversized unique maps.
Re-rendering the complete mission at download time would abandon existing leg
cache reuse and introduce heavy browser work into ready exports. Neither is the
selected approach. Whole-page rasterization is prohibited because it would lose
selectable text and independent chart/table content.

## Timeline drawing

Replace patterned rectangle fills with a solid background and clipped vector
diagonal strokes for unavailable transport intervals. Preserve the existing
hatch colors, spacing, stroke width, direction, and phase in the SVG coordinate
system. Keep clipping local to the exact interval rectangle, with unique clip
identifiers across legs and pages. Do not introduce SVG filters or a replacement
timeline bitmap.

Keep exact UTC geometry, all interval boundaries, transport states, labels,
unknown-state behavior, overall posture colors, and SOF/AR bands. Adjacent
intervals may share drawing resources, but their canonical identities and
evidence mappings remain unchanged. Shared strokes must not hatch quiet gaps,
unknown intervals, or an available lane.

The delivered PDF must contain vector timeline content without the repeated 922
by 185 background images or bottom strips. Verify nested Form XObjects and their
resources; a top-level image count cannot establish this requirement. Timeline
complexity may increase vector commands with interval count, but it must not
multiply full-background raster streams.

## Raster sizing

Use a shared policy of 300 raster pixels per printed inch for customer maps and
the logo. The document uses 96 CSS pixels per inch and 72 PDF points per inch.
Compute raster dimensions independently as `ceil(css_dimension * 300 / 96)`,
using the final measured placement. Do not change the page scale, CSS card size,
or document context's device scale factor to achieve this reduction; those also
affect layout and diagnostic previews.

### Logo

Preserve the original brand artwork as the master. Generate a deterministic 263
by 263 PNG derivative for the current 84 by 84 CSS-pixel header placement, using
high-quality resampling. Store the derivative alongside the master and bundle it
with the production renderer. Use its actual `image/png` MIME type. Keep the
circular CSS clip and the existing size, alignment, colors, and white corner
treatment. PNG introduces no additional lossy encoding step.

Hash the derivative actually embedded in the document. Renderer identity must
also cover the master, sizing policy, and renderer code so a changed asset or
policy cannot reuse an old oversized fragment. Preserve other uses of the master
artwork. Screen and print comparisons must confirm that small logo text and
edges remain acceptable to Brian before accepting the resized derivative.

### Maps

Measure each primary page's map card after font/image readiness and pagination,
then render at the dimensions derived from that card. A 280 by 270 CSS-pixel
card becomes an 875 by 844 pixel raster, replacing a 1920 by 1857 raster. Keep
the current PNG encoding; JPEG quality tuning is outside this design.

The final card measurement governs the accepted map. If pagination or map
fallback changes the available card dimensions, update the map render before
final verification within the existing shared deadline. Missing maps follow the
existing fallback and diagnostic contracts; continuation pages do not gain maps.

Preserve the route aspect ratio, complete route framing, endpoints, boundary
overlays, markers, and label identities. Scale pixel-based framing insets,
marker sizes, line widths, and label placement from their display-space sizes so
the smaller raster does not change the effective layout. Check the viewport
validation rules against the calculated sizes. Rendering fewer pixels must not
cause a previously supported complete map to become unavailable or lose labels.

Record the actual viewport and PNG hash in the existing map render evidence.
Reject invalid placement dimensions through the current safe render failure
path; do not silently fall back to the fixed 1920-pixel export size.

## Assembly and provenance

After appending the captured leg fragments in mission order, deduplicate
identical reusable image streams and their dependencies, including color
profiles, masks, and nested form resources. Identity includes image dimensions,
pixel data, color space, decode parameters, and masks; matching raw stream bytes
alone does not authorize merging images with different rendering semantics.
Different route maps remain distinct. Identical reusable content within a leg
and across independently rendered legs must share the final PDF resource.

Use the repository's supported pypdf version. Do not assume one invocation of
its deduplication helper completes dependency deduplication. Choose an ordering
or bounded convergence strategy that resolves references before declaring
reusable assets shared; tests must inspect the resulting PDF resource graph.
Avoid an unbounded optimization loop. Check cancellation between stages and
preserve the existing ownership and cleanup behavior.

Deduplication occurs before final serialization and publication. Preserve page
order, 960 by 540 point dimensions, embedded fonts, selectable text, chart/table
geometry, and warning content. Keep hashes of the original qualified leg PDFs in
their fragment reports. Compute the final delivered PDF hash from the bytes
after deduplication; retain the existing evidence page rebasing and schema.

Renderer revision already hashes renderer code, Python preparation code, and
brand assets. Cover the new derivative and raster policy through that mechanism
and test both cached-leg invalidation and prepared-ZIP invalidation. Old ready
downloads must not remain current after the renderer revision changes. A ready
export still assembles captured artifacts without running maps or a browser.

## Verification and acceptance

Automated regressions must cover these contracts:

- Many unavailable intervals across three lanes retain exact timing and hatch
  appearance, with no repeated timeline background raster streams, including
  resources nested inside Form XObjects.
- Independent leg fragments that each contain the logo and shared resources
  assemble to one reusable logo image. Different maps, masks, and color spaces
  remain distinct. Include continuation pages and mixed leg ordering.
- Raster dimensions follow measured display size at 300 pixels per inch,
  including fractional CSS sizes and layout changes. The shipped logo derivative
  has the correct format, dimensions, MIME type, and asset hash.
- All text, page assignments, row/cell validation, dimensions, warning
  semantics, evidence schemas, fragment provenance, and final artifact hashes
  remain valid.
- Renderer/asset changes invalidate current cached fragments and prepared ZIPs;
  ready export reuse, cancellation, and safe omission behavior continue to work.

Keep a reusable sanitized mission fixture with at least three independently
rendered legs, five pages, many unavailable intervals, and distinct route maps.
Record total bytes, image-stream bytes, raster dimensions, and reusable-object
counts for both the baseline and candidate. Size regressions must catch repeated
resources and oversized rasters, using the measured fixture baseline and these
structural contracts. Do not use 5 MB as a universal test assertion.

For lossless assembly changes, require identical extracted text and zero RGB
pixel difference on every page at screen resolution and 300 DPI. For the vector
hatch replacement and resized rasters, compare every page at those resolutions,
inspect timeline hatch detail, logo edges/text, route labels, and map framing,
and obtain Brian's visual approval. Pixel-error statistics supplement the
rendered comparisons; they are not a substitute for readability review.

Run offline and online exports through the production backend, Nginx, and
browser on the resulting `dev` integration baseline, including the retained
private five-page itinerary fixture. Preserve original and candidate exports,
exact byte/page counts, text and image inventories, duplicate resource groups,
and every-page visual comparisons in private Forge evidence. Measure ZIP size
separately and verify unchanged members, manifest, evidence bytes/contracts, and
import round-trips. Keep private inputs and operational details out of Git.

Apply repository-required checks and production acceptance to the implementation
candidate. Use an isolated acceptance project, explicit wall-clock limits,
ownership records, and verified teardown. This specification does not authorize
implementation, merge, or a claim that any mailbox size limit has been met.
