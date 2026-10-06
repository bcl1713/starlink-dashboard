# Overview precipitation radar

Enable **Configuration → Overview → Weather → Precipitation radar** to show
current precipitation on the native globe. It is off by default. The saved
setting applies to every Overview display; visible windows read it every five
seconds. No weather control or manual refresh is needed on Overview.

Overview shows a passive weather status, the observed frame's UTC time and age,
a precipitation legend, and linked RainViewer attribution. Hatching means no
radar coverage, including the polar regions outside Web Mercator; transparent
radar within coverage means no reported precipitation. Weather remains visible
on the night side and follows the globe as you rotate, zoom, or enter
fullscreen.

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

The layer uses observed precipitation from RainViewer's past radar frames, zoom
2, 512-pixel tiles, and provider coverage masks. It does not display a forecast,
cloud cover, wind, turbulence, icing, or an aviation hazard advisory. METAR
flight categories and SIGMET polygons are possible future aviation layers; each
needs its own data source, freshness rules, and approved scope.

[RainViewer's API terms](https://www.rainviewer.com/api.html) target personal,
educational, and small community use, require visible linked attribution, and
provide no availability guarantee. Check the provider's current terms before a
commercial deployment. The globe includes the attribution automatically.

Provider acquisition is shared across displays in one backend worker. Metadata
is cached for five minutes. The server limits actual attempts to 90 per rolling
minute, four active exchanges, and 32 pending acquisitions. Failed acquisitions
have a 30-second cooldown, respecting bounded provider retry guidance. The PNG
cache retains at most 48 tiles and 64 MiB of compressed bytes. Only the latest
and previous eligible radar frames and the current coverage generation are
served. Browser image work is limited to four concurrent operations and a
45-second complete-load deadline. GPU atlas storage stays within 48 MiB without
mipmaps.

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
