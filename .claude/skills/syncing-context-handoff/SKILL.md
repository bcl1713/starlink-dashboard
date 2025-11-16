---
name: syncing-context-handoff
description:
  Synchronizes PLAN.md, CONTEXT.md, CHECKLIST.md, HANDOFF.md, and
  LESSONS-LEARNED.md for the current feature branch so they reflect the true
  current state and a new session can resume easily.
---

# Syncing context and handoff

## Purpose

This skill keeps plan-related documentation consistent and maintains a clear
handoff summary so:

- The current session has accurate context.
- A future session can resume work on this branch with minimal ramp-up.
- Existing docs are updated rather than duplicated or overwritten.

## When to use

Use this skill:

- After a working session using `executing-plan-checklist`.
- Before ending a conversation or context window.
- After significant changes in scope, design, risks, or dependencies.

## Tool usage expectations

This skill uses tools to:

- Inspect current git branch.
- Read/write markdown files.
- Stage, commit, and push documentation updates.

---

## Template usage

When creating HANDOFF.md for the first time, this skill MUST use:

- HANDOFF template: `syncing-context-handoff/templates/HANDOFF.template.md`

Template placeholders:

- `{{branch_name}}`
- `{{slug}}`
- `{{folder}}`
- `{{date_iso}}`

The skill MUST NOT overwrite an existing HANDOFF.md from scratch; it should only
use the template on first creation.

For `dev/LESSONS-LEARNED.md`:

- This skill assumes the file already exists, created by
  `planning-feature-work`.
- It MUST NOT create or overwrite `dev/LESSONS-LEARNED.md`.
- If missing, it MUST report this as unexpected state and recommend re-running
  the planner to restore it.
- It may only append new dated entries.

---

## Workflow

### 1. Determine slug and locate docs

1. Inspect the current git branch.
2. If the branch name matches `feat/<slug>`, `fix/<slug>`, or `chore/<slug>`:
   - Extract `<slug>`.
3. On this branch, attempt to read:
   - `dev/active/<slug>/PLAN.md` (if present).
   - `dev/active/<slug>/CONTEXT.md` (if present).
   - `dev/active/<slug>/CHECKLIST.md` (if present).
   - `dev/active/<slug>/HANDOFF.md` (if present).
   - `dev/LESSONS-LEARNED.md` (shared; expected to exist).

If PLAN/CONTEXT/CHECKLIST are missing, this skill should not create them; that
is the planner’s job. It can still create HANDOFF.md if missing.

---

### 2. Reconcile documents with reality

Ask the user, briefly:

- Have any tasks been completed or abandoned since the last checklist update?
- Has the current phase or scope changed?

Then:

- Update CHECKLIST.md so that `- [x]` / `- [ ]` reflects reality.
- If PLAN.md has any notion of phase or status, update it to match the current
  state.
- Append new dependencies, tradeoffs, or constraints to CONTEXT.md.
- Append new lessons (if any) to `dev/LESSONS-LEARNED.md`.

Make minimal, targeted edits; preserve existing useful content.

---

### 3. Update or create HANDOFF.md

1. If `dev/active/<slug>/HANDOFF.md` exists:
   - Update it in place.
2. If it does not exist:
   - Create it from `syncing-context-handoff/templates/HANDOFF.template.md`.

HANDOFF.md must include:

- Overview: one short paragraph describing the work.
- Current status:
  - Phase and high-level progress.
- Next actions:
  - 3–5 actionable bullets, ideally referencing specific checklist items.
- Open questions / risks / blockers.
- References:
  - Repo name (if known).
  - Branch name.
  - Paths to PLAN, CONTEXT, CHECKLIST.
  - PR URL(s), if any.

A new session should be able to read HANDOFF.md first and quickly understand
what to do next.

---

### 4. Lessons learned

If new cross-cutting lessons emerged during the session:

- Ensure `dev/LESSONS-LEARNED.md` exists.
  - If it is missing, report that and recommend planner re-run.
- Append entries at the end of the "Entries" section using:
  - `- [YYYY-MM-DD] Short lesson description (optional link to PR/commit/path)`

---

### 5. Commit & push documentation updates

- Stage updated docs (PLAN, CONTEXT, CHECKLIST, HANDOFF, LESSONS-LEARNED as
  applicable).
- Commit with a message like:
  - `chore: sync planning and handoff docs for <slug>`
- Push the current branch.

---

### 6. Output

Provide:

- The full updated HANDOFF.md.
- A summary of which other docs changed.
- Guidance that a future session on this branch should:
  - Read HANDOFF.md first.
  - Then CHECKLIST.md.
  - Then PLAN/CONTEXT as needed.
