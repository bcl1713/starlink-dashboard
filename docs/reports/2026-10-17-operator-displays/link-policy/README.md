# Documentation link-checker policy follow-up

Requested after the review comment on PR #374: external documentation failures
are nonblocking, while internal files and anchors remain required. This changes
verification tooling only. Backend/frontend product source and the existing
synthetic Docker/browser acceptance candidate remain unchanged.

The canonical static gate now runs `tools/check_docs_links.py`. Its offline
file-only pass explicitly includes file URLs despite the legacy ignore rule and
checks fragments. Internal nonzero results, missing executables and timeouts
fail the gate. The separate HTTP/HTTPS pass retains Lychee's report and emits a
CI warning on failure, with ten-second requests, no retries and a two-minute
process bound. Other static checks still fail normally; CI remains a thin caller
of `tools/verify static`.

Validation with pinned Lychee 0.20.1:

- Full local canonical static gate passed. All 1,122 internal links passed;
  external failures were visible as warnings (15 timeouts in this run).
- Static policy/link tests: 12 passed, including nine new link-policy tests.
- Broader quality-gate, workflow, typing and link regressions: 29 passed, one
  deselected. The deselected recursive backend-dispatch test would run the whole
  backend suite again; that suite is covered by the required backend CI gate.
- Real Lychee tests reject missing internal files and missing anchors even with
  a `file://*` ignore, accept valid local anchors, and treat an unreachable
  local HTTP endpoint as advisory. Failure-injection tests also cover internal
  versus external missing-executable and process-timeout handling.
- Independent read-only review found no critical or important issues. Its minor
  timeout/missing-tool coverage suggestion was implemented.

`static.log` and `policy-tests.log` retain the results. The previous static
failure in the parent report remains historical evidence; this documented policy
resolves that external-link blocker without bypassing required CI. Final-head CI
and merge status are recorded on the PR and parent issue after they finish. No
service or worker was started for this follow-up.
