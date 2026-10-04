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

Propagator version, license and independent coordinate fixture verification will
be recorded during Task 3.
