# Checklist: Phase 8 - Wrap-Up & PR

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Phase:** 8 - Wrap-Up & PR
**Status:** Not Started

> This checklist covers final cleanup, verification, documentation updates, and PR preparation.

---

## Phase 8 Overview

**Goal:** Finalize documentation, prepare PR, and hand off.

**Exit Criteria:**
- PLAN.md updated to "Completed"
- CONTEXT.md finalized
- CHECKLIST.md fully completed
- PR created and ready for review

---

## 8.1: Code Quality Verification

### 8.1.1: Run linter on frontend

- [ ] Run ESLint:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run lint
  ```
- [ ] Fix any linting errors
- [ ] Verify no files exceed 350-line limit
- [ ] Expected: Zero linting errors

### 8.1.2: Run formatter on frontend

- [ ] Run Prettier:
  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner prettier --write src/
  ```
- [ ] Verify all files formatted consistently
- [ ] Expected: Code formatted according to .prettierrc

### 8.1.3: Run type checking on frontend

- [ ] Run TypeScript compiler:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run build
  ```
- [ ] Fix any type errors
- [ ] Expected: TypeScript compilation successful

### 8.1.4: Verify no TODOs remain in code

- [ ] Search for TODO comments:
  ```bash
  rg -i "TODO" /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner/src/
  rg -i "FIXME" /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner/src/
  rg -i "HACK" /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner/src/
  ```
- [ ] Remove or resolve all TODO/FIXME/HACK comments
- [ ] Expected: No temporary comments in code

---

## 8.2: Verify 350-Line Limit Compliance

### 8.2.1: Check all files

- [ ] Run line count check:
  ```bash
  find /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner/src -name "*.ts" -o -name "*.tsx" | xargs wc -l | sort -rn | head -20
  ```
- [ ] Verify no file exceeds 350 lines
- [ ] If any file exceeds limit, refactor it
- [ ] Expected: All files <= 350 lines

### 8.2.2: Verify ESLint enforces limit

- [ ] Open `frontend/mission-planner/.eslintrc.json`
- [ ] Verify rule exists:
  ```json
  "rules": {
    "max-lines": ["error", 350]
  }
  ```
- [ ] Expected: ESLint will catch violations in future

---

## 8.3: Build Verification

### 8.3.1: Build frontend for production

- [ ] Run production build:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run build
  ```
- [ ] Verify build completes without errors
- [ ] Check build output size
- [ ] Expected: Production build successful

### 8.3.2: Test production build locally

- [ ] Preview production build:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run preview
  ```
- [ ] Open preview URL in browser
- [ ] Test basic functionality
- [ ] Expected: Production build works correctly

### 8.3.3: Build Docker image for frontend

- [ ] Build frontend Docker image:
  ```bash
  docker compose build mission-planner
  ```
- [ ] Verify image builds successfully
- [ ] Expected: Docker image ready

### 8.3.4: Test full Docker Compose stack

- [ ] Bring up full stack:
  ```bash
  docker compose down && docker compose up -d
  ```
- [ ] Wait for services to be healthy:
  ```bash
  docker compose ps
  ```
- [ ] Verify all services running:
  - [ ] starlink-location (backend)
  - [ ] prometheus
  - [ ] grafana
  - [ ] mission-planner (frontend)
- [ ] Open http://localhost:5173 and test
- [ ] Expected: Full stack operational

---

## 8.4: Documentation Finalization

### 8.4.1: Update PLAN.md status

- [ ] Open `dev/active/mission-leg-planning-ui/PLAN.md`
- [ ] Change status from "Phases 1-4 Complete, Phase 5 Ready" to "Completed"
- [ ] Add completion date
- [ ] Save file
- [ ] Expected: PLAN.md reflects completion

### 8.4.2: Review and finalize CONTEXT.md

- [ ] Open `dev/active/mission-leg-planning-ui/CONTEXT.md`
- [ ] Verify all files are documented
- [ ] Verify all dependencies are listed
- [ ] Verify all risks are documented
- [ ] Add any final notes or discoveries
- [ ] Save file
- [ ] Expected: CONTEXT.md is complete and accurate

### 8.4.3: Mark all checklist items complete

- [ ] Open `dev/active/mission-leg-planning-ui/CHECKLIST.md`
- [ ] Verify all phase checklists referenced
- [ ] Mark "Documentation Maintenance" section complete
- [ ] Mark "Pre-Wrap Checklist" items as complete
- [ ] Save file
- [ ] Expected: Main checklist fully completed

### 8.4.4: Update LESSONS-LEARNED.md if needed

- [ ] Open `dev/LESSONS-LEARNED.md`
- [ ] Add any new lessons from Phases 5-8
- [ ] Format properly with dates
- [ ] Save file
- [ ] Expected: Lessons documented for future reference

---

## 8.5: Create HANDOFF.md

### 8.5.1: Generate handoff document

- [ ] Create `dev/active/mission-leg-planning-ui/HANDOFF.md`
- [ ] Include sections:
  ```markdown
  # Handoff: Mission Leg Planning UI

  **Branch:** `feat/mission-leg-planning-ui`
  **Status:** Ready for Review
  **Date:** [YYYY-MM-DD]

  ## Summary

  Implemented hierarchical mission planning UI with multi-leg support, satellite configuration, AAR segments, and export/import functionality.

  ## What Changed

  ### Backend
  - Refactored Mission → MissionLeg
  - Added new Mission model as container
  - Created v2 API endpoints
  - Implemented package export/import

  ### Frontend
  - New React + TypeScript application
  - Mission list and creation UI
  - Leg configuration pages
  - Satellite transition editors
  - AAR segment editor
  - Export/import dialogs

  ## Testing

  - Backend: [X] tests passing, [Y]% coverage
  - Frontend: [Z] tests passing
  - E2E: Full workflow tested

  ## How to Use

  1. Start stack: `docker compose up -d`
  2. Open http://localhost:5173/missions
  3. Create mission, add legs, configure satellites
  4. Export/import mission packages

  ## Known Issues

  [List any known issues or limitations]

  ## Next Steps

  [Any recommended follow-up work]
  ```
- [ ] Fill in all placeholders
- [ ] Save file
- [ ] Expected: HANDOFF.md ready for reviewer

---

## 8.6: Pre-PR Verification

### 8.6.1: Run all tests one final time

- [ ] Backend tests:
  ```bash
  source backend/starlink-location/venv/bin/activate && pytest backend/starlink-location/tests/ -v
  ```
- [ ] Frontend unit tests:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run test
  ```
- [ ] E2E tests:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run test:e2e
  ```
- [ ] Expected: All tests pass

### 8.6.2: Verify git status is clean

- [ ] Check git status:
  ```bash
  git status
  ```
- [ ] Verify no uncommitted changes (except node_modules, .vite, etc.)
- [ ] If changes exist, commit them
- [ ] Expected: Working directory clean

### 8.6.3: Verify all commits pushed

- [ ] Push any remaining commits:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [ ] Verify branch is up to date with remote
- [ ] Expected: All commits pushed to remote

---

## 8.7: Create Pull Request

### 8.7.1: Generate PR description

- [ ] Create PR description based on PLAN.md and HANDOFF.md
- [ ] Include:
  - Summary of changes
  - Objectives achieved
  - Testing performed
  - Screenshots/demos
  - Breaking changes (if any)
  - Migration guide (if needed)
- [ ] Save to file or clipboard
- [ ] Expected: PR description ready

### 8.7.2: Create PR on GitHub

- [ ] Go to GitHub repository
- [ ] Click "New Pull Request"
- [ ] Select base: `main`, compare: `feat/mission-leg-planning-ui`
- [ ] Paste PR description
- [ ] Add labels (if applicable)
- [ ] Assign reviewers (if applicable)
- [ ] Create PR
- [ ] Expected: PR created successfully

### 8.7.3: Link PR in documentation

- [ ] Copy PR URL
- [ ] Add PR link to HANDOFF.md
- [ ] Commit and push HANDOFF.md update
- [ ] Expected: Documentation references PR

---

## 8.8: Final Cleanup

### 8.8.1: Archive planning documents

- [ ] Verify all documents are in `dev/active/mission-leg-planning-ui/`
- [ ] Optionally move to `dev/completed/mission-leg-planning-ui/` (after PR merge)
- [ ] Expected: Documents organized

### 8.8.2: Celebrate completion

- [ ] Review what was built
- [ ] Acknowledge effort and quality
- [ ] Expected: Feature complete and ready for review! 🎉

---

## Final Commit

- [ ] Stage all final changes:
  ```bash
  git add dev/active/mission-leg-planning-ui/
  ```
- [ ] Commit:
  ```bash
  git commit -m "chore: finalize mission-leg-planning-ui feature

  - Update PLAN.md to Completed status
  - Finalize CONTEXT.md and CHECKLIST.md
  - Add HANDOFF.md for reviewer
  - All tests passing
  - Documentation complete
  - Ready for review

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 8"
  ```
- [ ] Push:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [ ] Expected: Feature branch finalized and ready for PR review

---

## Status

- [ ] All Phase 8 tasks completed
- [ ] Code quality verified
- [ ] 350-line limit enforced
- [ ] Build successful
- [ ] Documentation finalized
- [ ] PR created
- [ ] Ready for review
