# Acceptance Platform Structural Typing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every candidate-added `type: ignore` directive through
structural types while preserving all acceptance-platform behavior and
final-evidence guarantees.

**Architecture:** Platform-owned typed failure carriers replace dynamically
augmented caught exceptions. Core functions narrow optional resources at the
boundary, while tests use typed fixture/adaptor seams rather than invalid
construction, method reassignment, or unchecked JSON mutation. A repository
policy regression blocks new suppression directives in the candidate delta.

**Tech Stack:** Python 3.13, dataclasses, typing protocols/callables, pytest,
Git diff policy check.

**Spec:**
`docs/superpowers/specs/2026-09-25-acceptance-platform-structural-typing-design.md`

## Global Constraints

- Remove all 34 `type: ignore` directives added in the
  `6b96dcc532f4d0728e7cfe41716976e6f795ca1d..HEAD` candidate delta.

- Do not add `type: ignore`, per-file checker exclusions, blanket `Any`, or
  `cast(Any, ...)` replacements.

- Preserve candidate-SHA binding, content-aware final build policy, browser
  ownership/flags, 1920×1080 DPR1 WebGL2 acceptance, cleanup semantics, visible
  route/POI requirements, and explicit degraded-history behavior.

- Preserve bounded artifacts, primary-error causality, and fail-closed
  cleanup/evidence publication.

- No runtime, Docker, browser, network, or final-lane commands during
  implementation tasks.

- Documentation impact is limited to this plan/spec; no
  operator/API/runbook/release-policy changes are needed.

## Review Focus

- A caught ordinary `ValueError` retains `compose.output.log` without changing
  its causal error classification.

- A supervised build failure retains typed supervision and diagnostics even when
  ledger metadata is malformed.

- A missing topology override/ledger object fails before dereference and does
  not reach build/startup.

- Test doubles still provoke each final fail-closed path without mutating
  immutable production contracts.

- The policy check detects a newly added `type: ignore` in any candidate file,
  including tests.

---

## Companion documents

- [Tasks 1–2: Typed failure metadata and typed test fixtures](2026-09-25-acceptance-platform-structural-typing-tasks-1-2.md)
- [Task 3: Candidate suppression policy and verification evidence](2026-09-25-acceptance-platform-structural-typing-task-3.md)
