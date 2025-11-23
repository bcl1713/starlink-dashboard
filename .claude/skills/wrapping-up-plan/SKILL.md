---
name: wrapping-up-plan
description:
  Finalizes work for the current feature branch by validating checklist
  completion, updating docs, auto-committing, creating a PR, merging it when
  approved, archiving the dev folder, and pushing a cleanup commit.
---

# Wrapping up plan

## Purpose

This skill completes a plan end-to-end by:

- Verifying that all checklist tasks are complete.
- Updating PLAN.md, CONTEXT.md, HANDOFF.md, and LESSONS-LEARNED.md.
- Committing and pushing documentation updates.
- Creating a PR automatically for the feature branch.
- Updating the PR description with outcome details.
- Merging the PR when tools indicate it is approved and mergeable.
- Removing the dev folder:
  - Deleting `dev/active/<slug>/` to keep the codebase clean.
- Pushing a final cleanup commit to the default branch.

## When to use

Use this skill when:

- You are on a feature branch.
- `dev/active/<slug>/CHECKLIST.md` has no remaining `- [ ]` items.
- The work is believed to be functionally complete.

## Tool usage expectations

This skill uses tools to:

- Inspect current branch and repo state.
- Read and write markdown files.
- Run git add/commit/push.
- Interact with GitHub (or similar) to create/update/merge PRs.
- Move files and folders within the repo.

---

## Using LESSONS-LEARNED.md

This skill:

- Reads `dev/LESSONS-LEARNED.md` if it exists.
- Does **not** create or overwrite the file.
- If the file is missing, reports this as unexpected state and suggests
  re-running the planner on a future work item to restore it.
- Appends final lessons as dated entries when appropriate.

---

## Workflow

### 1. Determine slug and locate docs

1. Inspect the current branch and extract `<slug>` from:
   - `feat/<slug>`, `fix/<slug>`, or `chore/<slug>`.
2. On this branch, read:
   - `dev/active/<slug>/PLAN.md` (if present).
   - `dev/active/<slug>/CONTEXT.md` (if present).
   - `dev/active/<slug>/CHECKLIST.md` (required).
   - `dev/active/<slug>/HANDOFF.md` (if present).
   - `dev/LESSONS-LEARNED.md` (if present).

If CHECKLIST.md is missing, wrap-up cannot proceed and this should be reported.

---

### 2. Validate completion

1. Parse CHECKLIST.md and ensure all items are `- [x]`.
2. Ask the user once:
   - Whether all tests defined in PLAN/CONTEXT have been run.
   - Whether acceptance criteria are met.
3. If anything is incomplete:
   - Abort wrap-up and advise returning to `executing-plan-checklist`.

---

### 3. Update existing docs

Update docs **in place**; do not create new plan/context/checklist files.

- **PLAN.md**:
  - Add or update a status/outcome section marking the plan as **Completed**
    with the current date.
  - Summarize what was delivered and any deviations from the initial plan.
- **CONTEXT.md**:
  - Append any final architecture decisions, tradeoffs, or caveats.
- **HANDOFF.md** (if present):
  - Update status to indicate that work on this branch is complete (or pending
    merge).
  - Add PR URL once created.
  - List any follow-on ideas that should be separate future plans.
- **LESSONS-LEARNED.md** (if present):
  - Append any final lessons as dated entries in the standard format.

---

### 4. Commit and push documentation updates

On the feature branch:

- Stage updated docs.
- Commit with a message like:
  - `chore: finalize docs for <slug>`
- Push the branch to the remote.

---

### 5. Create or update the PR automatically

Using GitHub (or equivalent) tools:

1. Check if a PR already exists for this branch targeting the main/default
   branch.
2. If a PR exists:
   - Update its description to reference:
     - PLAN.md outcome.
     - Completed checklist.
     - Key implementation notes from CONTEXT.md.
3. If a PR does not exist:
   - Create one with:
     - Title:
       - `feat: <summary>` for feature branches.
       - `fix: <summary>` for fix branches.
       - `chore: <summary>` for chore branches.
     - Body:
       - Summary of what was delivered.
       - Implementation details.
       - Confirmation that checklist is fully complete.

Then:

- Insert the PR URL back into PLAN.md and HANDOFF.md (if present).
- Commit and push any doc updates that reference the PR URL.

---

### 6. Merge when ready

If tools expose review status and CI results:

- When PR is approved and mergeable:
  - Merge the PR using the project’s preferred strategy.
  - Optionally delete the remote feature branch if project conventions allow.

If tools do not expose this information:

- Leave the PR open and:
  - Update HANDOFF.md to state that the PR is “awaiting review and merge”.

---

### 7. Remove dev folder and cleanup commit

Once the PR is merged and the default branch is up to date:

1. Check out the default/main branch and pull the latest changes.
2. Remove the folder on disk:
   - Delete: `dev/active/<slug>/`
3. Update any project-level indices/README as needed to reference:
   - The merged PR.
   - The completion of work for this slug.

Then:

- Stage these changes.
- Commit with a message like:
  - `chore: remove dev folder for <slug>`
- Push the default branch.

---

### 8. Output

The skill should summarize for the user:

- The feature branch name and slug.
- The PR URL.
- Whether the PR is open or merged.
- Confirmation that the dev folder has been removed.
- Note that final docs (PLAN.md, CONTEXT.md, CHECKLIST.md, HANDOFF.md) are
  preserved in the merged PR history.

After this skill runs and the PR is merged, the work is considered fully wrapped
and the dev folder is cleaned up to keep the codebase uncluttered.
