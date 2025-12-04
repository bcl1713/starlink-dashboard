---
name: planning-feature-work
description:
  Plans a new feature, fix, or refactor by clarifying requirements, creating a
  dedicated branch, and generating or updating PLAN.md, CONTEXT.md,
  CHECKLIST.md, and LESSONS-LEARNED.md. Use at the beginning of any new work.
---

# Planning feature work

## Purpose

This skill creates a complete, consistent plan for new work. It:

- Asks clarifying questions about the requested feature, fix, or refactor.
- Generates a short slug and creates a new branch named `feat/<slug>`,
  `fix/<slug>`, or `chore/<slug>`.
- Checks whether `dev/active/<slug>/` already exists.
- Reuses existing PLAN.md, CONTEXT.md, CHECKLIST.md if present.
- Creates missing plan files from templates in this directory.
- Ensures a project-wide `dev/LESSONS-LEARNED.md` file exists (creating it from
  a template if missing).
- Produces a clear, multi-phase plan and a junior-developer-friendly checklist.

## When to use

Use this skill when:

- Starting new feature, bug-fix, or refactor work.
- Replanning work that exists but lacks proper docs.
- Standardizing ad-hoc work into a structured plan.

## Tool usage expectations

This skill is expected to use tools (configured by the surrounding system) to:

- Inspect current git state (current branch, default branch, remotes).
- Create and switch branches.
- Read and write files in the repo.
- Stage, commit, and push plan documents.

It does not ask the user to run git commands manually.

---

## Workflow

### 1. Clarify the work request

Ask only the minimum necessary clarifying questions about:

- Objective and motivation.
- Acceptance criteria.
- Constraints and dependencies.
- Relevant repos or services.

Do **not** ask the user to paste existing file contents.  
Do **not** ask the user for plan file paths; derive them from the slug.

Once clarified, explicitly state that scope is locked for this work item.

---

### 2. Generate slug, branch, and folder

1. Create a short, kebab-case slug from the request, e.g.
   `avatar-customization`.
1. Choose branch name based on type:
   - Features: `feat/<slug>`
   - Bug fixes: `fix/<slug>`
   - Refactors/tooling: `chore/<slug>`
1. Create the branch from the latest main (or default) branch using git tools.
1. Define the dev folder as: `dev/active/<slug>/`.
   - If it exists, reuse it.
   - If missing, create it.

All plan documents for this work live under `dev/active/<slug>/` on the feature
branch.

---

### 3. Check for existing docs

On the feature branch, check for:

- `dev/active/<slug>/PLAN.md`
- `dev/active/<slug>/CONTEXT.md`
- `dev/active/<slug>/CHECKLIST.md`

Behavior:

- If files exist, read them and update in place, preserving useful history.
- If any are missing, create them using the templates in
  `planning-feature-work/templates/`.

---

### 4. PLAN.md

PLAN.md must contain:

- Header:
  - Title.
  - Date.
  - Owner (user or team).
  - Repo (if known).
  - Branch.
  - Dev folder path.
- Executive summary:
  - 3–7 sentences, understandable to a non-technical stakeholder.
- Objectives:
  - A bullet list of testable outcomes.
- Phases (typically 3–6):
  - For each phase:
    - Name.
    - Description.
    - Entry criteria.
    - Exit criteria.

When updating an existing PLAN.md, modify only what is necessary to reflect the
current scope and phases. Do not discard useful historical context.

---

### 5. CONTEXT.md

CONTEXT.md must contain:

- Background and motivation.
- Relevant code paths and modules.
- Dependencies (APIs, env vars, services, feature flags).
- Constraints and assumptions.
- Risks.
- Testing strategy:
  - Exactly what “done and verified” means.
- References:
  - Issues, design docs, PRs as they become available.

When updating, append or adjust sections; do not rewrite from scratch unless
clearly necessary.

---

### 6. CHECKLIST.md (junior-friendly and exhaustive)

CHECKLIST.md is the authoritative execution guide and must assume the executor
is a **brand-new junior developer with no prior knowledge of the repo or
codebase**.

It MUST:

- Use markdown checkboxes (`- [ ]`) and nested checklist items for subtasks.
- Break work into **atomic, non-overlapping tasks**:
  - Avoid vague tasks like “implement feature”.
  - Each task should accomplish a single logical operation.
- For every code-editing task, specify:
  - Exact file path.
  - What to add/change/remove with concrete snippets or diffs.
- For every command, provide the exact command:
  - e.g. `git checkout feat/avatar-customization`, not “switch to feature
    branch”.
- Include expected results after important steps:
  - e.g. “After running this command, you should see X”.
- Include test instructions at logical points.
- Include tasks to keep:
  - PLAN.md updated if phases or goals change.
  - CONTEXT.md updated when dependencies or constraints change.
  - dev/LESSONS-LEARNED.md updated when significant lessons emerge.
- Include frequent commits:
  - Provide explicit suggested commit messages.
  - Require a commit (and push) after each logical unit of work.
- Always refer to the feature branch, never instruct direct work on main.

The planning skill MUST replace the placeholder Implementation section of the
template with concrete tasks tailored to this specific work item.

---

### 7. LESSONS-LEARNED.md (ensure existence)

This skill is responsible for ensuring that `dev/LESSONS-LEARNED.md` exists.

- Check if `dev/LESSONS-LEARNED.md` exists at the repo root.
- If it does **not** exist:
  - Create it from
    `planning-feature-work/templates/LESSONS-LEARNED.template.md`.
- Do **not** add any lesson entries here; this skill only ensures the file
  exists.
- Execution, handoff, and wrap-up skills will append dated entries later.

---

### 8. Template usage

When creating files for the first time, this skill MUST use the templates in its
own directory:

- PLAN.md → `planning-feature-work/templates/PLAN.template.md`
- CONTEXT.md → `planning-feature-work/templates/CONTEXT.template.md`
- CHECKLIST.md → `planning-feature-work/templates/CHECKLIST.template.md`
- LESSONS-LEARNED.md →
  `planning-feature-work/templates/LESSONS-LEARNED.template.md` (if missing)

Template placeholders:

- `{{branch_name}}` → actual git branch name.
- `{{slug}}` → slug portion of the branch.
- `{{folder}}` → `dev/active/{{slug}}/`.
- `{{date_iso}}` → current date in YYYY-MM-DD.
- `{{owner}}` → username or team name.
- `{{title}}` → human-readable title for the work.

The skill MUST load the template file, substitute placeholders, and write the
result. It MUST NOT create plan docs with ad-hoc content.

---

### 9. Commit and push plan docs

After creating or updating PLAN.md, CONTEXT.md, CHECKLIST.md, and ensuring
LESSONS-LEARNED.md exists, this skill MUST:

- Stage the changed files.
- Commit them on the feature branch with a message like:
  - `chore: create plan for <slug>`
- Push the branch to the remote.

The user should not have to run these commands manually.

---

### 10. Output

The skill should summarize for the user:

- The slug and branch name.
- The dev folder path.
- Which docs were created or updated.
- That the branch has been pushed and is ready for execution via
  `executing-plan-checklist`.
