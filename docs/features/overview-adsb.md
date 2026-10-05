# Optional ADS-B aircraft

Configuration's **ADS-B aircraft layer** defaults off. It adds global eligible
positions independently of the own aircraft, route, history, links and warnings.
Smaller batched glyphs follow observed ground track. Earth blocks rear-side
markers and selection. Stale glyphs have a ring; included labels show **◷
Stale**. Only saved included aircraft have permanent labels, using callsign,
registration, then hex. Crowded labels retain every identity rather than
becoming a count.

Click a visible glyph or focus its **Details for HEX** button to open
read-only observations. Close/Escape restores focus; details remain available in
native fullscreen. Camera drag over five CSS pixels cannot select, and selection
does not alter camera or follow state. Expiry, exclusion or disabling closes
details. The ADS-B legend appears while the layer has unexpired contacts,
independently of camera occlusion. Map placement does not imply a measured
altitude.

See [shared aircraft settings](system.md#shared-ads-b-aircraft-settings) and the
[ADS-B API](../api/endpoints/overview-adsb.md) for precedence and freshness.

## Aircraft marker tuning

Own aircraft uses a white-blue luminous chevron above the scene's lines and
other markers; Earth still hides it on the far side. Other aircraft use warm
amber. Both retain their CSS-pixel size when zooming. Outer glow follows the
chevron's edges, with overlapping halos capped instead of adding brightness.

For live visual experiments, open `/overview?markerDebug=1`. The collapsible
**Aircraft marker tuning** panel controls own and other aircraft sizes, core
brightness, colored edge width, glow width divisor and glow strength. Glow width
is each aircraft's size divided by the divisor (default **3**): **5 px** for own
aircraft and about **3.33 px** for traffic. **Copy settings** exports the
numbers for review; the text box also supports manual copying on browsers
without clipboard access. **Reset defaults** restores the code's values. These
experimental settings last until the Overview page reloads and are not shared
with other viewers.
