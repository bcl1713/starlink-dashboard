# Orbital provider review

Reviewed 2026-10-04 before provider implementation. No live GP catalog was
requested during this review.

The [CelesTrak usage policy](https://celestrak.org/usage-policy.php) requires
on-demand downloads, one download per update, shared caching for viewers behind
one address, and stopping automated queries on any non-200 response while
reporting the failure for human investigation. GP updates use a two-hour interval.
The experiment persists each attempt before network I/O, enforces a minimum
7,200-second interval including failures, honors longer Retry-After values,
and suspends on every non-200 response until explicit operator resume.
No automatic redirects or HTTP retries are enabled. Timeout/transport errors
retain the cooldown. Diagnostic reads create no viewer demand.

The [GP format documentation](https://celestrak.org/NORAD/documentation/gp-data-formats.php)
supports JSON OMM keywords and decimal IDs up to nine digits. JSON may omit
redundant EARTH/TEME/UTC/SGP4 metadata; those documented defaults are accepted.
Explicit incompatible metadata is rejected. Missing numeric elements are never
defaulted. Provider UTC epochs lacking a zone are interpreted as UTC.

The planned endpoint is an example, never a link-check target:

```text
https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=JSON
```

The application limit is 16 MiB streamed bytes and a 20-second timeout. Accepted
objects are capped at 16,384 using numeric ID order. A download cannot replace
the last good catalog with an empty or corrupt response. Public orbital elements
provide context; they do not establish serving spacecraft or internal routing.

## Propagator and reference fixture

Pinned `satellite.js` 7.1.0 (MIT), reviewed 2026-10-04 using its
[maintainer repository](https://github.com/shashwatak/satellite-js), npm metadata,
and package source. Its ESM export exposes `json2satrec`, SGP4 `propagate`,
`gstime` and `eciToEcf`; string catalog IDs are retained. Unused descriptive
metadata is empty for the TypeScript OMM interface; no mean elements are invented.
Vite module-worker packaging is verified by the Task 3 build.

Coordinate tests use [Vallado's verification case](https://celestrak.org/publications/AIAA/2006-6753/)
5, mirrored in the reference implementation's
[verification elements](https://raw.githubusercontent.com/brandon-rhodes/python-sgp4/master/sgp4/SGP4-VER.TLE)
and [published vectors](https://raw.githubusercontent.com/brandon-rhodes/python-sgp4/master/sgp4/tcppver.out).
At epoch 2000-06-27 18:50:19.733568 UTC the published TEME position is
`[7022.46529266, -1400.08296755, 0.03995155]` km. An independent rotation using
the Vallado GMST polynomial gives angle `3.4691723423794016` radians and ECEF
`[-6198.557667319622, 3585.1267686862966, 0.03995155]` km. The test allows
2 metres for millisecond Date precision. OMM numeric fields transcribe the
historical verification elements; application propagation uses OMM exclusively.
