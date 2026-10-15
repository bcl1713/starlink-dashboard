# Acceptance Platform Structural Typing Design

## Purpose

PR #183 has valid candidate-bound final browser evidence at
`a1cd78fe3cb2e9b2f38f67b0a30bbe5c919b5f29`, but final review found 34 newly
introduced `type: ignore` directives in the acceptance platform and its test
surface. The artifact-gating policy prohibits publishing a candidate that adds
such suppressions. This design removes those suppressions by expressing the
existing runtime contracts structurally, without weakening acceptance policy or
changing product behavior.

## Scope

The change is confined to:

- typed propagation of retained platform diagnostics on classified failures;
- typed build-supervision failure metadata;
- explicit optional topology/override handling;
- typed test seams and fixture builders for Compose, runner, model, and
  evidence mutations.

It applies to the acceptance platform implementation and its tests only. It
must preserve the sealed evidence schema, candidate-SHA binding, content-aware
build supervision, browser lifecycle, route/POI observation, and degraded
history semantics.

Documentation impact is limited to this design and its implementation plan.
No operator, user, API, runbook, release-policy, or architecture documentation
changes are needed because observable behavior and operational commands remain
unchanged.

## Design

### 1. Classified error metadata is a declared contract

The health, Compose, and runner flows currently retain bounded diagnostics by
attaching attributes such as `platform_artifacts`, `platform_cleanup_error`,
and `build_supervision` to caught exceptions. Replace dynamic assignment to
built-in or opaque exception values with platform-owned typed failure carriers.

A carrier must:

- retain the original causal exception through chaining;
- declare the bounded artifact mapping and optional cleanup/supervision metadata
  as normal fields;
- expose only the metadata consumed by the existing sealing paths; and
- preserve the original primary classification and fail-closed cleanup behavior.

Callers must use the carrier type rather than suppressing missing-attribute
errors. No generic `Any`, monkey-patched exception attributes, or new
`type: ignore` directives are permitted.

### 2. Optional resources are narrowed at their boundary

Topology override paths, build ledger handles, and optional browser inputs must
be checked or narrowed before use. A function that requires a rendered override
or ledger must accept a non-optional typed value, and its caller must classify a
missing value before calling it. The resulting error path remains bounded and
non-final.

This removes `union-attr`, `arg-type`, and `attr-defined` suppressions by making
absence explicit rather than by asserting it away.

### 3. Test mutation uses typed adapters, not instance reassignment

Tests currently replace executor methods, mutate immutable candidate keys, and
modify JSON-shaped payloads through untyped indexing. Replace these patterns
with explicit test-only builders/adapters:

- construct profile/model fixtures with valid typed descriptors rather than
  passing `None` into required fields;
- construct configurable executor instances through their declared injection
  seams rather than assigning a different callable to a method after creation;
- construct tampered typed payload copies with checked nested access rather than
  unchecked dictionary indexing;
- use typed wrappers for ledger and evidence-writer fault injection; and
- use precise callable signatures when wrapping rendering, journey, or sealing
  functions.

Tests must retain their current adversarial behavior: each still proves the
relevant fail-closed branch, not merely a fixture construction detail.

### 4. Enforcement and acceptance criteria

The implementation must remove every candidate-added `type: ignore` directive
from these paths; it must not replace them with blanket `cast(Any, ...)`,
per-file checker exclusions, or a policy exception.

Automated acceptance must prove:

- the focused acceptance-platform suites remain green;
- the exact candidate delta from the pre-typing base has zero added
  `type: ignore` directives, checked by an executable policy regression;
- exception/evidence and build-supervision failure paths retain their bounded
  metadata and original causal classification;
- optional resource absence remains fail-closed;
- adversarial test seams still exercise their intended error conditions; and
- final evidence semantics, browser ownership, SHA attribution, and cleanup are
  unchanged.

A new candidate will require fresh pushed-SHA verification, health, static, and
final acceptance evidence before PR #183 can be merged into `dev`.

## Non-goals

- No change to user-facing mission, ETA, POI, route, or overview behavior.
- No change to browser flags, WebGL policy, viewport contract, final timeouts,
  cache controls, Dockerfile build order, or evidence inventory.
- No relaxed linting, type-checking, or publication policy.
- No release or merge to `main`.
