# Overview precipitation radar

Enable **Configuration → Overview → Weather → Precipitation radar** to show
current precipitation on the native globe. It is off by default. The saved
setting applies to every Overview display; visible windows read it every five
seconds. No weather control or manual refresh is needed on Overview.

Overview shows a passive weather status, the observed frame's UTC time and age,
a precipitation legend, and linked attribution for the displayed source.
Hatching means no radar coverage, including the polar regions outside Web
Mercator; transparent radar within coverage means no reported precipitation.
Weather remains visible on the night side and follows the globe as you rotate,
zoom, or enter fullscreen.

## Automatic refresh and freshness

An enabled, visible display checks immediately, then approximately every five
minutes. Each successful manifest starts the next five-minute interval. The
browser displays a frame only after all 16 radar tiles and all coverage tiles
are ready. It replaces the complete frame at once. An unchanged validated frame
reuses the existing imagery.

Frames through 20 minutes old are current. Older frames remain explicitly stale
until 60 minutes, when imagery is removed. A failed refresh immediately marks
retained eligible imagery stale. Failed initial loads show weather unavailable.
Failures never extend the original expiry. Coverage expires at UTC midnight and
must be replaced before radar can be displayed again. Weather uses real UTC,
independently of mission playback and the browser's wall-clock setting.

Hidden displays stop acquiring weather. Returning to a visible display or
recovering the network requires fresh confirmed settings. If settings cannot be
confirmed for 15 seconds, the display hides radar and reports unavailable.
Disabling weather removes it from visible displays on the next settings poll;
the server cancels its provider work before the save completes. The base globe,
mission controls, aircraft, links, and telemetry continue during weather
failure.

## Data source and limits

The layer initially uses observed precipitation from RainViewer's past radar
frames, 512-pixel tiles and provider coverage masks. A complete zoom-2 atlas
remains available while the native camera selects up to eight visible regional
tile pairs at higher zoom, bounded by the manifest's maximum (initially 7).
Demand is sampled at most four times per second and must remain stable for 400
ms. Small camera movements retain eligible overlapping imagery.

Radar opacity is a fixed 0.40; coverage hatching remains independently 0.17.
Regional detail publishes only after both radar and coverage decode for the
displayed frame. Missing detail uses the complete fallback and does not change
frame age or mark otherwise confirmed imagery stale. Refreshing the complete
frame clears old detail atomically; source/schema changes also invalidate
incompatible tiles. Human-readable provenance changes update metadata without
forcing downloads. It does not display a forecast, cloud cover, wind,
turbulence, icing, or an aviation hazard advisory. METAR flight categories and
SIGMET polygons are possible future aviation layers; each needs its own data
source, freshness rules, and approved scope.

[RainViewer's API terms](https://www.rainviewer.com/api.html) target personal,
educational, and small community use, require visible linked attribution, and
provide no availability guarantee. Check the provider's current terms before a
commercial deployment. The globe includes the attribution automatically.

Provider acquisition is shared across displays in one backend worker. Metadata
advertises a separate radar path for each timestamp; the server preserves its
validated opaque identifier instead of constructing a path from the timestamp.
Metadata is cached for five minutes. The server limits actual attempts to 90 per
rolling minute, four active exchanges, and 32 pending acquisitions.
Higher-detail work uses at most 30 of those attempts and two exchanges; coarse
imagery and metadata retain priority. Failures have a 30-second cooldown,
respecting bounded provider retry guidance. The PNG cache retains at most 48
tiles and 64 MiB of compressed bytes. Only the latest and previous eligible
radar frames and the current coverage generation are served. Browser image work
is limited to four concurrent operations and a 45-second load deadline, with at
most two detail operations. Browser-owned decoded canvases/bitmaps share a 96
MiB allocation budget. GPU storage uses 32 MiB for the complete pair plus 16 MiB
for eight fixed detail slots, without mipmaps. Detail textures are disposed
before coarse replacement so its peak also remains within 48 MiB.

## Operation

Settings persist in `data/settings/overview-weather.json` with an increasing
revision. Saves are atomic and idempotent. Corrupt/unreadable settings fail
closed and return a service error. Restore a valid saved file to recover; do not
edit it concurrently with a settings save. Keep one backend worker because the
provider budget and cache are process-local.

Weather requires verified HTTPS access to `api.rainviewer.com` and
`tilecache.rainviewer.com`. The server accepts only those provider paths, pins
public numeric IPs while verifying the original TLS host, and applies bounded
HTTP/PNG validation. Provider content is served through local API routes; the
browser never contacts RainViewer directly.

See the [weather endpoint reference](../api/endpoints/overview-weather.md) and
[production acceptance runner](../../tools/acceptance/overview-weather/README.md).

Configuration → Aviation weather → Flight-level atmosphere enables NOAA GFS
winds and air temperature, sharing one pressure or interpolated flight level and
forecast horizon across displays. Surface is explicitly unsupported. The
Overview context is passive: expand it for actual run/valid UTC, level and
legends. Confirmed requested level/horizon remains visible while loading or
unavailable, separately from actual run/valid UTC and modeled analysis or
numerical-model forecast. Stale products keep their original deadline; expired
products disappear even if subsequent catalog requests fail.

Temperature uses the native globe's nearest-filtered signed packed texture,
manual conservative bilinear sampling and a fixed −80 to +40 °C palette with
clamped ends; wire temperature remains K. Categorical masks never interpolate
into valid data. Meteorological wind FROM barbs use rounded knots, filled 50 kt
pennants, 10 kt full feathers, 5 kt half feathers and calm circles. At most
2,000 deterministic equal-area samples are shown; this thinning is disclosed.
The temperature surface renders below radar hatching; model glyphs render below
bulletin and operational markers and do not intercept report picking.

Model assets remain optional. Missing data or admission failures mean unknown
weather and preserve core globe, telemetry and planning controls. Shared
settings confirm saves only after the server responds and refresh on visible
displays every five seconds; model catalogs refresh each minute while visible
and online.
