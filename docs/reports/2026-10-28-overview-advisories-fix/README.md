# Live Overview advisory availability

Base: remote `dev` at `f0c1bd490cc8ab084bca481e93257f062788172c`.

## Reproduction and correction

The normal Operator events API returns mission-wide coverage. In a synthetic
Live mission with an active leg and an unprepared future leg, its HTTP 200
snapshot contains:

| Source                            | Freshness                      | Alignment |
| --------------------------------- | ------------------------------ | --------- |
| `operator`                        | fresh                          | aligned   |
| `planning:lifecycle:demo-mission` | fresh                          | aligned   |
| `model:leg-a`                     | fresh                          | aligned   |
| `model:future-leg`                | unknown (timeline unavailable) | unaligned |

Overall coverage is correctly `partial`. Overview previously interpreted that as
an active-leg failure, displaying an unavailable banner beside a valid X-Band
advisory indefinitely. Its event selection was already active-leg-only.

Overview now checks the active model, all its dependencies, and shared sources.
A partial snapshot is accepted only when an excluded other-leg source explains
the partial status. Missing active models, active prerequisites/PoP failures,
shared failures, unknown coverage, and unexplained partial coverage still warn.
Event classification, freshness, timing, and acknowledgement remain unchanged.

This reproduces a concrete Live failure path, not an inspection of the user's
running deployment. No production/device access was used.

## Verification

- Failing frontend regression reproduced the banner before the change.
- Focused frontend: 30 tests passed across projection, hook, and presentation.
- Focused backend production-source tests: 35 passed.
- Aggregate Operator backend suite: 574 passed.
- Production frontend TypeScript/Vite build passed (existing browser
  externalization and large-chunk warnings).
- Scoped ESLint, Prettier, Black, Ruff, and whitespace checks passed.
- Complete frontend suite passed in eight bounded shards on Node 22.22.2: 326
  files and 2,286 tests, every discovered file completed exactly once. Earlier
  unsharded runs were incomplete; a later instrumented unsharded run progressed
  normally through 51 files before its diagnostic time limit. No memory or
  process-limit events occurred. The earlier silence is unexplained.
- Independent review found no critical or important issues.
- System Chromium rendered the actual API snapshot through the production
  projection/component before and after the change. The false warning cleared;
  an injected active-source failure still warned; acknowledgement hid the item.
  See `browser-results.json` and `active-leg.png`. This is a component browser
  control with captured API data, not full application/Nginx acceptance.

Full production Docker/Nginx acceptance was attempted but the backend image's
Playwright browser download received HTTP 403 `Domain forbidden` from the
configured network. The existing end-to-end test now explicitly requires no
unavailable banner during healthy Live operation, but could not run here. The
acceptance runner verified its containers, networks, volumes, images, listeners,
and children removed. The local component-browser server was stopped. No merge,
deployment, or changes overlapping the metrics PR #432 were made.
