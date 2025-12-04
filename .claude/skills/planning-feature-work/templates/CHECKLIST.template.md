# Checklist for {{slug}}

**Branch:** `{{branch_name}}`  
**Folder:** `{{folder}}`  
**Status:** In Progress  
**Skill:** executing-plan-checklist

> This checklist is intentionally extremely detailed and assumes the executor
> has no prior knowledge of the repo or codebase. Every step must be followed
> exactly, in order, without combining or skipping.

---

## Initialization

- [ ] Ensure you are on the correct branch:
  - [ ] Run:

    ```bash
    git branch
    ```

  - [ ] Confirm that the current branch line is:

    ```text
    * {{branch_name}}
    ```

  - [ ] If you are on a different branch, switch with:

    ```bash
    git checkout {{branch_name}}
    ```

---

## Implementation Tasks

> The planning skill MUST replace this section with concrete tasks that:
>
> - Use explicit file paths
> - Provide full code snippets or diffs
> - Include exact shell commands
> - Include expected outcomes after each step
> - Include a commit and push after each logical unit

- [ ] Placeholder task — to be replaced by planning-feature-work skill.

---

## Documentation Maintenance

- [ ] Update PLAN.md if any phase boundaries changed.
- [ ] Update CONTEXT.md if new files, dependencies, assumptions, or risks were
      discovered.
- [ ] Update LESSONS-LEARNED.md when something surprising or important happens.

---

## Verification Tasks

- [ ] Run test suite:

  ```bash
  npm test
  ```

- [ ] Manually verify flows described in CONTEXT.md -> Testing Strategy.
- [ ] Confirm acceptance criteria from PLAN.md -> Objectives.

---

## Pre-Wrap Checklist

All of the following must be checked before handoff to `wrapping-up-plan`:

- [ ] All tasks above are marked `- [x]`.
- [ ] No TODOs remain in code.
- [ ] Dev server runs without warnings or errors.
- [ ] Tests pass.
- [ ] PLAN.md updated to reflect implementation progress.
- [ ] CONTEXT.md updated with any final clarifications.
