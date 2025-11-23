---
name: executing-plan-checklist
description:
  Use this skill to implement work on any feature/fix/chore branch. Executes one
  checklist task at a time for the current feature branch by automatically
  locating dev/active/<slug>/CHECKLIST.md, applying changes, committing after
  each step, and updating the checklist immediately. Use once a plan exists.
---

# Executing plan checklist

## Purpose

This skill orchestrates plan execution safely and predictably by:

- Detecting the current branch.
- Extracting `<slug>` automatically.
- Loading PLAN.md, CONTEXT.md, CHECKLIST.md, and LESSONS-LEARNED.md from their
  respective locations.
- Treating the checklist as authoritative and written for an inexperienced
  junior developer.
- Orchestrating ONE checklist task at a time through delegation to sub-agents.
- Requesting confirmation before delegating each task.
- Delegating all code changes, file edits, and command execution to Haiku
  sub-agents (preserving orchestrator context).
- Committing and pushing after each step completes.
- Marking the task `- [x]` immediately in CHECKLIST.md.
- Maintaining awareness of LESSONS-LEARNED.md and passing it to sub-agents.

## When to use

Use this skill to implement work on any feature/fix/chore branch **after**
`planning-feature-work` has run for that work item.

## Tool usage expectations

**Orchestrator (Sonnet) uses tools to:**

- Inspect the active git branch.
- Read PLAN.md, CONTEXT.md, CHECKLIST.md, and LESSONS-LEARNED.md files.
- Update CHECKLIST.md to mark tasks complete.
- Run git add/commit/push after each delegated task completes.
- Delegate task execution to sub-agents via the Task tool.

**Sub-agents (Haiku) receive:**

- The exact checklist task to execute.
- Full content of PLAN.md, CONTEXT.md, and LESSONS-LEARNED.md.
- Explicit instruction to check LESSONS-LEARNED.md when encountering errors or
  blockers.
- Direction to report back: success/failure, files changed, and any new lessons
  learned.
- Sub-agents have full tool access for code edits, file operations, and command
  execution.

**Result:** The orchestrator context remains clean and focused on coordination,
while sub-agents handle all implementation work in disposable contexts.

The user should not have to run any commands manually.

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
   - LESSONS-LEARNED.md → `dev/LESSONS-LEARNED.md` (repo root)
   - HANDOFF.md → `dev/active/<slug>/HANDOFF.md` (if exists)

If CHECKLIST.md does not exist, surface an error and suggest running
`planning-feature-work` for this branch.

Load and retain the full content of all four files for use in sub-agent
delegation and local updates.

---

### 2. Identify next unchecked task

1. Parse HANDOFF.md if it exists.
2. Parse CHECKLIST.md.
3. Find the first line with `- [ ]`.
4. Include any direct subtasks under this item as context.

If there are no remaining `- [ ]` items:

- Inform the user that the checklist is complete.
- Suggest invoking `wrapping-up-plan` on this branch.

---

### 3. Present the step and request confirmation

For the identified checklist item:

- Show the exact checklist line and any subtasks.
- Describe how you plan to delegate it to a sub-agent:
  - What the sub-agent will receive (task, PLAN, CONTEXT, LESSONS-LEARNED).
  - What the sub-agent will do (files to edit, commands to run, tests to
    execute).
  - What the orchestrator expects to receive back (success/failure, files
    changed, lessons learned).
- Ask the user to confirm before delegating.

If a checklist item is ambiguous or insufficiently detailed:

- Pause and ask the user for clarification.
- Update the checklist **in place** to make the item explicit and
  junior-friendly.
- Only then proceed to delegation.

---

### 4. Delegate task to sub-agent

Once confirmed, delegate to a Haiku sub-agent via the Task tool:

**What to pass to the sub-agent:**

- The exact checklist task (from CHECKLIST.md).
- Full content of PLAN.md.
- Full content of CONTEXT.md.
- Full content of LESSONS-LEARNED.md (with explicit instruction: "Check this
  file if you encounter errors or blockers").
- Instruction: "Execute this task exactly as specified in the checklist. Report
  back: (1) success or failure, (2) list of files changed, (3) any new lessons
  learned that should be added to LESSONS-LEARNED.md."
- Grant full tool access to the sub-agent (Read, Edit, Write, Bash, etc.).

**Sub-agent behavior:**

- Follows the checklist exactly.
- Uses all necessary tools to make code changes, run commands, and edit files.
- If it encounters an error, checks LESSONS-LEARNED.md for prior solutions.
- Reports back: success/failure, files changed, new lessons (if any).

**Orchestrator behavior (while delegating):**

- Waits for sub-agent to complete.
- Receives the task result and file list from sub-agent.
- Does NOT edit source code or run implementation commands itself.

---

### 5. Mark task complete, handle lessons, commit, and push

After the sub-agent returns:

**If the sub-agent reports new lessons:**

1. Append each new lesson to `dev/LESSONS-LEARNED.md` in the Entries section
   using the format:
   - `- [YYYY-MM-DD] Short lesson description (optional link to PR/commit/path)`

**For all completions:**

1. Change the corresponding `- [ ]` to `- [x]` in CHECKLIST.md (and any relevant
   subtasks).
2. If PLAN.md or CONTEXT.md should be updated (per the task or lesson), do so
   now.
3. Stage all changed files (code from sub-agent + updated docs).
4. Commit with a message like:
   - `chore: complete checklist step: <short summary>`
5. Push the current feature branch to the remote.

Show the updated snippet of CHECKLIST.md to the user for visibility.

---

### 6. Iterate or stop

After each completed task:

- Reload CHECKLIST.md to detect the next unchecked item.
- Ask the user if they want to proceed to the next task.
- If yes, repeat from step 2 (identify next task).
- If no, suggest running `syncing-context-handoff` to keep docs and HANDOFF.md
  in sync.

**Note:** Between iterations, the orchestrator has access to fresh CHECKLIST.md
state and can make informed decisions about task sequencing.

---

## Using LESSONS-LEARNED.md

This skill MUST treat `dev/LESSONS-LEARNED.md` as:

- A shared, project-wide, append-only log.
- Already created by `planning-feature-work`.
- A resource that MUST be passed to sub-agents when delegating tasks.

**Orchestrator rules:**

- It MUST NOT create or overwrite `dev/LESSONS-LEARNED.md`.
- If the file is missing, it MUST surface an error and suggest re-running the
  planner to restore it.
- It MUST read the full file before each sub-agent delegation.
- It MAY only append new entries at the end of the "Entries" section using:
  - `- [YYYY-MM-DD] Short lesson description (optional link to PR/commit/path)`

**Sub-agent rules (via instruction):**

- Sub-agents MUST be given the full content of LESSONS-LEARNED.md.
- Sub-agents MUST be instructed: "If you encounter errors or blockers, check the
  LESSONS-LEARNED.md file for prior solutions or patterns."
- Sub-agents MUST report back any new lessons learned during task execution.
- Sub-agents MUST NOT directly edit LESSONS-LEARNED.md; the orchestrator handles
  this.
