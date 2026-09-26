# V2 Acceptance Browser Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make final V2 acceptance use the profile-certified headed browser
lifecycle and preserve prompt, bounded adapter failures instead of masking them
as timeouts.

**Architecture:** Extract a reusable platform-owned browser session lifecycle
from health so final acceptance can allocate, prove, retain, and clean a headed
Xvfb/CDP session without accepting caller-controlled browser authority. Make
adapter subprocess failures carry bounded stdout/stderr into sealed failure
evidence. Ensure the V2 adapter explicitly disconnects its CDP attachment after
either success or failure.

**Tech Stack:** Python 3.11, pytest, subprocess/Xvfb/Chromium CDP, Node ESM,
Playwright, Docker Compose.

**Spec:**
`docs/superpowers/specs/2026-09-24-v2-acceptance-browser-recovery-design.md`

## Global Constraints

- Use only the administrator-provisioned profile executable; do not download,
  install, or substitute a browser.

- Final browser evidence must be headed Xvfb, native 1920×1080 viewport/raster,
  DPR 1; no headless or emulated substitution.

- Product contracts remain product-only and cannot contain
  browser/process/port/cleanup authority.

- Preserve original adapter errors in bounded sealed diagnostics; do not replace
  an exited adapter failure with a timeout.

- Final runner execution is one tracked 900-second monitored process with
  durable logs; no automatic final retry.

- All temporary browser, display, Compose, profile, task-root, listener, and
  process cleanup must be verified; retain volumes and durable evidence.

- Documentation impact is in scope; no product UI or mission semantics change.

## Review Focus

- A caller provides a loopback CDP URL for final acceptance: the runner must not
  accept it as a substitute for the profile-owned headed session.

- The browser starts and `/json/version` responds but neutral screenshot/metrics
  are not exact 1920×1080/DPR 1: fail before final build claim.

- The adapter writes a useful error then leaves a CDP socket open: the process
  must terminate promptly and runner evidence must retain that exact bounded
  error.

- Adapter stdout/stderr exceeds its retention budget: fail closed without
  unbounded memory/file growth.

- Browser/Xvfb or Compose cleanup fails after an adapter failure: preserve the
  primary failure, downgrade the claim, and record cleanup independently.

---

## Companion documents

- [Tasks 1–2: Final browser lifecycle and adapter failure evidence](2026-09-24-v2-acceptance-browser-recovery-tasks-1-2.md)
- [Tasks 3–4: Operator workflow and exact-head evidence](2026-09-24-v2-acceptance-browser-recovery-tasks-3-4.md)
