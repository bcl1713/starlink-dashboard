---
name: executing-plan-checklist
description:
  Executes one checklist task at a time for the current feature branch by
  automatically locating dev/active/<slug>/CHECKLIST.md, applying changes,
  committing after each step, and updating the checklist immediately. Use once a
  plan exists.
---

# Executing plan checklist

## Purpose

This skill executes a plan safely and predictably by:

- Detecting the current branch.
- Extracting `<slug>` automatically.
- Loading PLAN.md, CONTEXT.md, and CHECKLIST.md from `dev/active/<slug>/`.
- Treating the checklist as authoritative and written for an inexperienced
  junior developer.
- Executing ONE checklist task at a time.
- Requesting confirmation before performing each task.
- Applying file changes directly via tools.
- Committing and pushing after each step.
- Marking the task `- [x]` immediately in CHECKLIST.md.

## When to use

Use this skill to implement work on any feature/fix/chore branch **after**
`planning-feature-work` has run for that work item.

## Tool usage expectations

This skill uses tools to:

- Inspect the active git branch.
- Read and update markdown files and source files.
- Run git add/commit/push after each completed task.

The user should not have to run these commands manually.

---

## Template usage

This skill does **not** create PLAN/CONTEXT/CHECKLIST/HANDOFF files and
therefore does **not** read any templates. It only reads and updates existing
markdown files created by other skills.

For `dev/LESSONS-LEARNED.md`, it:

- Assumes the file already exists, created by `planning-feature-work`.
- Does not create or overwrite the file.
- Only appends new entries when lessons arise.

---

## Workflow

### 1. Determine slug and file paths

1. Inspect the current git branch name.
2. If branch matches `feat/<slug>`, `fix/<slug>`, or `chore/<slug>`:
   - Extract `<slug>` as everything after the first `/`.
3. Compute paths:
   - PLAN.md → `dev/active/<slug>/PLAN.md`
   - CONTEXT.md → `dev/active/<slug>/CONTEXT.md`
   - CHECKLIST.md → `dev/active/<slug>/CHECKLIST.md`

If CHECKLIST.md does not exist, surface an error and suggest running
`planning-feature-work` for this branch.

---

### 2. Identify next unchecked task

1. Parse CHECKLIST.md.
2. Find the first line with `- [ ]`.
3. Include any direct subtasks under this item as context.

If there are no remaining `- [ ]` items:

- Inform the user that the checklist is complete.
- Suggest invoking `wrapping-up-plan` on this branch.

---

### 3. Present the step and request confirmation

For the identified checklist item:

- Show the exact checklist line and any subtasks.
- Describe how you plan to execute it:
  - Files to edit.
  - Code or config changes.
  - Commands to run.
  - Tests to execute.
- Ask the user to confirm before proceeding.

If a checklist item is ambiguous or insufficiently detailed:

- Pause and ask the user for clarification.
- Update the checklist **in place** to make the item explicit and
  junior-friendly.
- Only then proceed.

---

### 4. Execute the task

Once confirmed:

- Apply code and config changes using tools.
- If the task implies updates to PLAN.md or CONTEXT.md, update those files as
  well.
- If the task yields a significant lesson:
  - Append a dated entry to `dev/LESSONS-LEARNED.md` in this format:
    - `- [YYYY-MM-DD] Short lesson description (optional link to PR/commit/path)`

---

### 5. Mark task complete, commit, and push

For each task:

1. Change the corresponding `- [ ]` to `- [x]` in CHECKLIST.md (and any relevant
   subtasks).
2. Stage all changed files (code + docs).
3. Commit with a message like:
   - `chore: complete checklist step: <short summary>`
4. Push the current feature branch to the remote.

Show the updated snippet of CHECKLIST.md to the user for visibility.

---

### 6. Iterate or stop

After each step:

- Ask the user if they want to proceed to the next unchecked checklist item.
- If yes, repeat from identifying the next task.
- If no, suggest running `syncing-context-handoff` to keep docs and HANDOFF.md
  in sync.

---

## Using LESSONS-LEARNED.md

This skill MUST treat `dev/LESSONS-LEARNED.md` as:

- A shared, project-wide, append-only log.
- Already created by `planning-feature-work`.

Rules:

- It MUST NOT create or overwrite `dev/LESSONS-LEARNED.md`.
- If the file is missing, it MUST surface an error and suggest re-running the
  planner to restore it.
- It MAY only append new entries at the end of the "Entries" section using:
  - `- [YYYY-MM-DD] Short lesson description (optional link to PR/commit/path)`
