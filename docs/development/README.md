# Development Guides

Start with [Contributing](../../CONTRIBUTING.md), the
[development workflow](workflow.md), and
[quality gates](../contributing/quality-gates.md). Use isolated worktrees based
on `origin/dev`; submit PRs against `dev` and retain open-PR worktrees without
keeping runtime resources alive.

## Current References

- [Release policy](release-policy.md) and
  [release baseline](../release-notes.md)
- [Managed-cloud Docker and scoped teardown](cloud-docker.md)
- [Architecture](../architecture/README.md) and
  [API reference](../api-reference-index.md)
- [Code quality](../code-quality-standards.md) and
  [focused testing](../contributing/testing-guide.md)
- [Issue 404 test-runtime assessment and session handoff](ci-404/README.md)
- [Acceptance platform](../operations/acceptance-platform.md)
- [Mission export preparation](mission-export-preparation.md)
- [Customer briefing exports](customer-briefing-exports.md) and
  [acceptance](customer-briefing-acceptance.md)
- [ADS-B provider acquisition](adsb-provider-acquisition.md) and
  [orbital provider policy](orbital-provider-policy.md)

## Historical Assistant References

[Claude Code notes](claude-code/README.md) and
[workflow examples](../workflows/index.md) describe earlier assistant
configurations. Named agents, slash commands and skills are not installed by
this repository; use the tools available in your session and the current
repository workflow above.
