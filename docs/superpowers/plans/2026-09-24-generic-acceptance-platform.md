# Generic Acceptance Platform Roadmap

> **For agentic workers:** Execute the linked plans in order with
> `superpowers:subagent-driven-development`. Each linked plan uses checkbox
> steps and ends in an independently reviewable deliverable.

**Goal:** Replace branch-owned acceptance orchestration with a certified generic
platform and prove it through the V2 mission-retirement product contract.

**Spec:**
`docs/superpowers/specs/2026-09-24-generic-acceptance-platform-design.md`

## Ordered Implementation Plans

1. [Foundation: product contracts and immutable browser bundles](2026-09-24-acceptance-platform-foundation.md)
2. [Execution: platform health, Compose isolation, and one-build ledger](2026-09-24-acceptance-platform-execution.md)
3. [Delivery: runner, V2 journey adapter, docs, and exact-head evidence](2026-09-24-acceptance-platform-delivery.md)

## Cross-Plan Constraints

- Preserve application behavior, deployment configuration, credentials, and live
  infrastructure.
- Keep branch contracts limited to product semantics. They cannot select browser,
  Docker, installer, timeout, Xvfb/CDP, evidence, retry, or cleanup policy.
- Keep source/test modules below roughly 300 lines; split by responsibility.
- A current platform health fingerprint is required before every product lane.
- A final build runs once for each profile checksum, candidate SHA, and contract
  checksum tuple; never use `up --build` or a duplicate final build.
- Browser provisioning never occurs in a branch acceptance run.
- Generated evidence remains outside the repository, checksum-bound, and verified
  after task-owned cleanup.

## Documentation Impact

The delivery plan adds platform operations documentation and V2 contract
instructions. No user-facing product, API, release, or architecture behavior is
changed.
