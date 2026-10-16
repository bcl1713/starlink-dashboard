# Release Documentation Refresh Plan

**Goal:** Reconcile current guides with the checked-out implementation and
clearly distinguish v1.0.0 from subsequent integration changes.

**Scope:** Documentation only; preserve dated implementation and acceptance
records as history. Maintain existing URLs when consolidating duplicate guides.

- [x] Create isolated `docs/v1-refresh` worktree from `origin/dev`.
- [x] Audit setup, deployment and troubleshooting against Compose and config.
- [x] Audit operator features and mission workflows against source and tests.
- [x] Audit APIs, schemas and architecture against registered routes and models.
- [x] Reconcile entry points, indexes, contributor guidance and release
      baseline.
- [x] Run Markdown/link and existing documentation checks; review the full diff.
      Handoff: push and submit a PR to `dev`; retain the worktree without
      runtime resources while review is open.

Independent documentation areas are audited in parallel with disjoint ownership.
The primary agent integrates findings and verifies the complete documentation.
