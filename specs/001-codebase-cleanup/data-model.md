# Data Model: Codebase Cleanup and Refactoring

**Feature**: 001-codebase-cleanup **Created**: 2025-12-02 **Version**: 1.0

## Overview

This document defines the core entities, relationships, and state machines for
tracking and managing the codebase cleanup refactoring process. These entities
support the systematic refactoring of 26+ files to achieve constitutional
compliance.

## Entity Definitions

### 1. Code File

**Description**: A source code or documentation file subject to constitutional
principles and refactoring requirements.

#### Code File: Attributes

| Attribute              | Type          | Required | Description                           |
| ---------------------- | ------------- | -------- | ------------------------------------- |
| `file_id`              | string (UUID) | Yes      | Unique identifier                     |
| `path`                 | string        | Yes      | Absolute path from repo root          |
| `line_count`           | integer       | Yes      | Current line count                    |
| `original_line_count`  | integer       | Yes      | Original line count                   |
| `language`             | enum          | Yes      | `python`, `ts`, `js`, `md`            |
| `module_type`          | enum          | Yes      | `api`, `service`, `component`...      |
| `violation_status`     | enum          | Yes      | Current state (see State Mach.)       |
| `refactoring_priority` | enum          | Yes      | `P0` to `P3` (see Rules)              |
| `violation_severity`   | enum          | Yes      | `critical`, `moderate`, `none`        |
| `estimated_effort`     | enum          | No       | `small` to `xlarge` (see definitions) |
| `has_justification`    | boolean       | No       | True if deferred (FR-004)             |
| `justification_reason` | string        | No       | Reason for deferral                   |
| `assigned_to`          | string        | No       | Assignee                              |
| `created_at`           | timestamp     | Yes      | Assessment time                       |
| `updated_at`           | timestamp     | Yes      | Last update                           |
| `metadata`             | JSON          | No       | Extra context (complexity etc.)       |

#### Code File: Relationships

- **Has Many** `Refactoring Task` (1:N) - A file may require multiple
  refactoring tasks (size reduction, documentation, SOLID principles)
- **Has Many** `Validation Check` (1:N) - A file undergoes multiple validation
  checks (line count, linting, type coverage)
- **Belongs To** `Pull Request` (N:1) - A file is refactored within one or more
  PRs (across iterations)

#### Code File: State Machine

```text
┌─────────────┐
│ unassessed  │  Initial state: File exists but not evaluated
└──────┬──────┘
       │ assessment_complete
       ↓
┌─────────────┐
│  violating  │  File violates one or more constitutional principles
└──────┬──────┘
       │ task_assigned
       ↓
┌─────────────┐
│ in_progress │  Refactoring task(s) are actively being worked on
└──────┬──────┘
       │ refactoring_complete
       ↓
┌─────────────┐
│ refactored  │  Code changes made, awaiting validation
└──────┬──────┘
       │ validation_pass
       ↓
┌─────────────┐
│  validated  │  All validation checks passed, compliant with constitution
└─────────────┘

       │ validation_fail (from refactored)
       ↓
┌─────────────┐
│  deferred   │  Refactoring deemed too risky or complex; documented per FR-004
└─────────────┘
```

**State Transition Rules**:

- `unassessed → violating`: Automated scan detects line count > 300 or linting
  failures
- `violating → in_progress`: Refactoring task created and assigned
- `in_progress → refactored`: PR merged with refactored code
- `refactored → validated`: All validation checks pass
- `refactored → deferred`: Validation reveals breaking changes or excessive risk
- `violating → deferred`: Evaluation determines refactoring unsafe; FR-004
  comment added

#### Code File: Validation Rules

1. **Line Count Constraint**: `line_count` must be ≤ 300 for `validated` state
   (or `has_justification` = true)
2. **Path Uniqueness**: `path` must be unique across all Code File entities
3. **Priority Assignment**: `refactoring_priority` calculated as:
   - `P0_critical`: `violation_severity = critical` AND
     `module_type IN (api, service)`
   - `P1_high`: `violation_severity = critical` OR
     (`violation_severity = moderate` AND `module_type IN (api, service)`)
   - `P2_medium`: `violation_severity = moderate` AND
     `module_type IN (component, documentation)`
   - `P3_low`: `violation_severity = none` but has documentation/style issues
4. **Effort Estimation**: Based on line count, complexity, and dependency
   analysis

#### Code File: Example Data

```json
{
  "file_id": "cf-001",
  "path": "backend/starlink-location/app/api/ui.py",
  "line_count": 3995,
  "original_line_count": 3995,
  "language": "python",
  "module_type": "api",
  "violation_status": "in_progress",
  "refactoring_priority": "P0_critical",
  "violation_severity": "critical",
  "estimated_effort": "xlarge",
  "has_justification": false,
  "justification_reason": null,
  "assigned_to": "claude-code-agent",
  "created_at": "2025-12-02T10:00:00Z",
  "updated_at": "2025-12-02T14:30:00Z",
  "metadata": {
    "endpoints_count": 47,
    "cyclomatic_complexity": 156,
    "dependencies": ["mission.routes", "services.poi_manager"]
  }
}
```

---

### 2. Refactoring Task

**Description**: A specific unit of work to bring one or more files into
constitutional compliance.

#### Refactoring Task: Attributes

| Attribute          | Type          | Required | Description                 |
| ------------------ | ------------- | -------- | --------------------------- |
| `task_id`          | string (UUID) | Yes      | Unique identifier           |
| `title`            | string        | Yes      | Task description            |
| `target_files`     | string[]      | Yes      | Target file paths           |
| `violation_type`   | enum          | Yes      | `size`, `doc`, `solid`...   |
| `estimated_effort` | enum          | Yes      | `small` to `xlarge`         |
| `actual_effort`    | integer       | No       | Hours spent                 |
| `status`           | enum          | Yes      | Current state (see Machine) |
| `priority`         | enum          | Yes      | `P0` to `P3`                |
| `assigned_to`      | string        | No       | Assignee                    |
| `pr_number`        | integer       | No       | GitHub PR number            |
| `dependencies`     | string[]      | No       | IDs of prerequisite tasks   |
| `blocked_by`       | string[]      | No       | IDs blocking this task      |
| `blocks`           | string[]      | No       | IDs dependent on this task  |
| `started_at`       | timestamp     | No       | Work start time             |
| `completed_at`     | timestamp     | No       | Completion time             |
| `created_at`       | timestamp     | Yes      | Creation time               |
| `updated_at`       | timestamp     | Yes      | Last update                 |
| `notes`            | string        | No       | Implementation notes        |

#### Refactoring Task: Relationships

- **Belongs To Many** `Code File` (N:M) - A task may refactor multiple related
  files; a file may require multiple tasks- **Has Many** `Validation Check`
  (1:N) - A task triggers validation checks upon completion
- **Belongs To** `Pull Request` (N:1) - A task is completed within a single PR
- **Depends On** `Refactoring Task` (N:M) - Tasks may have dependency
  relationships

#### Refactoring Task: State Machine

```text
┌─────────────┐
│   pending   │  Task created, not yet started
└──────┬──────┘
       │ start_task
       ↓
┌─────────────┐
│   blocked   │  Waiting for dependency tasks to complete
└──────┬──────┘
       │ dependencies_resolved
       ↓
┌─────────────┐
│ in_progress │  Actively being worked on
└──────┬──────┘
       │ submit_for_review
       ↓
┌─────────────┐
│  in_review  │  PR submitted, awaiting code review
└──────┬──────┘
       │ approve_pr
       ↓
┌─────────────┐
│  completed  │  PR merged, task done
└─────────────┘

       │ request_changes (from in_review)
       ↓
┌─────────────┐
│   rework    │  Changes requested, back to in_progress
└──────┬──────┘
       │ resubmit
       ↓
   (back to in_review)

       │ deem_too_risky (from blocked or in_progress)
       ↓
┌─────────────┐
│  deferred   │  Task too complex/risky; create follow-up issue
└─────────────┘
```

**State Transition Rules**:

- `pending → blocked`: Task has unresolved dependencies
- `pending → in_progress`: No blocking dependencies, work starts
- `blocked → in_progress`: All dependency tasks reach `completed` state
- `in_progress → in_review`: PR created and submitted
- `in_review → completed`: PR approved and merged
- `in_review → rework`: Changes requested by reviewer
- `rework → in_review`: Changes addressed, PR updated
- `blocked/in_progress → deferred`: Risk assessment deems task unsafe; follow-up
  issue created

#### Refactoring Task: Validation Rules

1. **Dependency Acyclic Constraint**: No circular dependencies allowed in
   `dependencies` graph
2. **Cannot Start Rule**: Task with `status = blocked` cannot transition to
   `in_progress` if any task in `dependencies[]` has
   `status NOT IN (completed, deferred)`
3. **PR Association**: Task with `status IN (in_review, completed)` must have
   non-null `pr_number`
4. **File Ownership**: All `target_files[]` must exist as Code File entities
5. **Completion Evidence**: Task with `status = completed` must have associated
   Validation Checks with `status = passed`

#### Refactoring Task: Example Data

```json
{
  "task_id": "task-001",
  "title": "Split ui.py into route modules (< 300 lines each)",
  "target_files": ["backend/starlink-location/app/api/ui.py"],
  "violation_type": "size",
  "estimated_effort": "xlarge",
  "actual_effort": null,
  "status": "in_progress",
  "priority": "P0_critical",
  "assigned_to": "claude-code-agent",
  "pr_number": null,
  "dependencies": [],
  "blocked_by": [],
  "blocks": ["task-002", "task-003"],
  "started_at": "2025-12-02T14:00:00Z",
  "completed_at": null,
  "created_at": "2025-12-02T10:30:00Z",
  "updated_at": "2025-12-02T14:00:00Z",
  "notes": "Plan: Extract 10 route groups into separate files under api/ui/. Maintain backward compatibility via __init__.py re-exports."
}
```

---

### 3. Validation Check

**Description**: An automated or manual verification that a requirement is met
for a Code File or Refactoring Task.

#### Validation Check: Attributes

| Attribute        | Type          | Required | Description                      |
| ---------------- | ------------- | -------- | -------------------------------- |
| `check_id`       | string (UUID) | Yes      | Unique identifier                |
| `requirement_id` | string        | Yes      | Spec requirement ID              |
| `check_type`     | enum          | Yes      | Validation type (see table)      |
| `target_entity`  | enum          | Yes      | Entity type validated            |
| `target_id`      | string        | Yes      | Entity ID                        |
| `status`         | enum          | Yes      | `pending`, `passed`, `failed`... |
| `automated`      | boolean       | Yes      | True if automated                |
| `evidence`       | JSON          | No       | Supporting data                  |
| `error_message`  | string        | No       | Failure reason                   |
| `executed_at`    | timestamp     | No       | Execution time                   |
| `executed_by`    | string        | No       | Executor (CI, Agent, User)       |
| `created_at`     | timestamp     | Yes      | Creation time                    |
| `updated_at`     | timestamp     | Yes      | Last update                      |

#### Check Types

| Check Type                | Description                                       | Automated | Requirement |
| ------------------------- | ------------------------------------------------- | --------- | ----------- |
| `line_count`              | Verify file ≤ 300 lines                           | Yes       | FR-001-003  |
| `black_formatting`        | Run Black on Python files                         | Yes       | FR-024      |
| `prettier_formatting`     | Run Prettier on TS/JS/Markdown                    | Yes       | FR-025, 028 |
| `eslint_validation`       | Run ESLint on TS/JS files                         | Yes       | FR-026      |
| `markdownlint_validation` | Run markdownlint-cli2 on Markdown                 | Yes       | FR-027      |
| `type_coverage`           | Check type hints (Python) or TypeScript stricture | Yes       | FR-005, 008 |
| `docstring_coverage`      | Verify docstrings on Python functions             | Yes       | FR-006      |
| `jsdoc_coverage`          | Verify JSDoc on exported TS/JS functions          | Yes       | FR-007      |
| `documentation_accuracy`  | Verify docs match implementation                  | No        | FR-013-017  |
| `smoke_test`              | Manual functional verification                    | No        | Assumption  |
| `solid_compliance`        | Review for SOLID violations (manual or tool)      | Partial   | FR-018-023  |

#### Validation Check: Relationships

- **Belongs To** `Code File` OR `Refactoring Task` OR `Pull Request` (N:1) - A
  check validates one entity
- **Triggered By** `Refactoring Task` (N:1) - Tasks trigger checks upon
  completion

#### Validation Check: State Machine

```text
┌─────────────┐
│   pending   │  Check queued, not yet executed
└──────┬──────┘
       │ start_check
       ↓
┌─────────────┐
│   running   │  Check currently executing
└──────┬──────┘
       │ check_complete
       ↓
┌─────────────┐
│   passed    │  Check succeeded
└─────────────┘

       │ check_failed (from running)
       ↓
┌─────────────┐
│   failed    │  Check did not pass
└─────────────┘

       │ skip_check (from pending)
       ↓
┌─────────────┐
│   skipped   │  Check not applicable (e.g., Python check on TS file)
└─────────────┘
```

**State Transition Rules**:

- `pending → running`: Check execution begins
- `running → passed`: Check criteria met
- `running → failed`: Check criteria not met
- `pending → skipped`: Check not applicable to target entity

#### Validation Check: Validation Rules

1. **Target Existence**: `target_id` must reference an existing Code File,
   Refactoring Task, or Pull Request
2. **Type Applicability**: Check type must be valid for target entity's language
   (e.g., `black_formatting` only for `language = python`)
3. **Evidence Requirement**: `status = passed` or `status = failed` must have
   non-null `evidence`
4. **Automated Consistency**: `automated = true` checks must have
   `executed_by = ci_system`

#### Validation Check: Example Data

```json
{
  "check_id": "vc-001",
  "requirement_id": "FR-001",
  "check_type": "line_count",
  "target_entity": "code_file",
  "target_id": "cf-001",
  "status": "failed",
  "automated": true,
  "evidence": {
    "current_line_count": 3995,
    "threshold": 300,
    "violation_severity": "critical"
  },
  "error_message": "File exceeds 300 line limit by 3695 lines",
  "executed_at": "2025-12-02T10:15:00Z",
  "executed_by": "ci_system",
  "created_at": "2025-12-02T10:00:00Z",
  "updated_at": "2025-12-02T10:15:00Z"
}
```

```json
{
  "check_id": "vc-002",
  "requirement_id": "SC-004",
  "check_type": "type_coverage",
  "target_entity": "refactoring_task",
  "target_id": "task-001",
  "status": "passed",
  "automated": true,
  "evidence": {
    "functions_checked": 47,
    "functions_with_type_hints": 47,
    "coverage_percent": 100
  },
  "error_message": null,
  "executed_at": "2025-12-02T16:00:00Z",
  "executed_by": "ci_system",
  "created_at": "2025-12-02T15:45:00Z",
  "updated_at": "2025-12-02T16:00:00Z"
}
```

---

### 4. Pull Request

**Description**: A GitHub pull request containing one or more Refactoring Tasks,
subject to validation checks before merge.

#### Attributes

| Attribute            | Type          | Required | Description                      |
| -------------------- | ------------- | -------- | -------------------------------- |
| `pr_id`              | string (UUID) | Yes      | Internal unique ID               |
| `pr_number`          | integer       | Yes      | GitHub PR number                 |
| `branch_name`        | string        | Yes      | Feature branch name              |
| `base_branch`        | string        | Yes      | Target branch                    |
| `title`              | string        | Yes      | PR title                         |
| `description`        | string        | No       | PR body/description              |
| `file_count`         | integer       | Yes      | Changed file count               |
| `lines_added`        | integer       | No       | Lines added                      |
| `lines_removed`      | integer       | No       | Lines removed                    |
| `status`             | enum          | Yes      | Current PR state                 |
| `smoke_test_results` | JSON          | No       | Manual test results              |
| `ci_status`          | enum          | Yes      | `pending`, `passed`, `failed`... |
| `approval_status`    | enum          | Yes      | Approval state                   |
| `approved_by`        | string        | No       | Reviewer                         |
| `created_at`         | timestamp     | Yes      | Creation time                    |
| `updated_at`         | timestamp     | Yes      | Last update                      |
| `merged_at`          | timestamp     | No       | Merge time                       |
| `closed_at`          | timestamp     | No       | Close time                       |

#### Relationships

- **Contains Many** `Refactoring Task` (1:N) - A PR completes 1-3 related tasks
- **Triggers Many** `Validation Check` (1:N) - A PR triggers CI validation
  checks
- **Modifies Many** `Code File` (N:M) - A PR changes multiple files

#### State Machine

```text
┌─────────────┐
│    draft    │  PR created but not ready for review
└──────┬──────┘
       │ mark_ready_for_review
       ↓
┌─────────────┐
│    open     │  PR open and awaiting review
└──────┬──────┘
       │ ci_checks_running
       ↓
┌─────────────┐
│ ci_pending  │  Automated checks running
└──────┬──────┘
       │ ci_pass
       ↓
┌─────────────┐
│   review    │  CI passed, awaiting human review
└──────┬──────┘
       │ approve
       ↓
┌─────────────┐
│  approved   │  Reviewer approved, ready to merge
└──────┬──────┘
       │ merge
       ↓
┌─────────────┐
│   merged    │  PR merged to base branch
└─────────────┘

       │ ci_fail (from ci_pending)
       ↓
┌─────────────┐
│  ci_failed  │  Automated checks failed, needs fixes
└──────┬──────┘
       │ push_fixes
       ↓
   (back to ci_pending)

       │ request_changes (from review)
       ↓
┌─────────────┐
│   rework    │  Changes requested, author making updates
└──────┬──────┘
       │ push_updates
       ↓
   (back to ci_pending)

       │ close_pr (from any state)
       ↓
┌─────────────┐
│   closed    │  PR closed without merging (abandoned or superseded)
└─────────────┘
```

**State Transition Rules**:

- `draft → open`: Author marks PR ready for review
- `open → ci_pending`: CI checks triggered on PR creation/update
- `ci_pending → review`: All CI checks pass
- `ci_pending → ci_failed`: One or more CI checks fail
- `ci_failed → ci_pending`: Author pushes fixes, CI re-runs
- `review → approved`: Reviewer approves PR
- `review → rework`: Reviewer requests changes
- `rework → ci_pending`: Author pushes updates
- `approved → merged`: PR merged to base branch
- `* → closed`: PR closed without merging

#### Lifecycle Constraints

1. **File Count Limit**: `file_count` should be ≤ 3 (per spec: 1-3 related
   files)
2. **CI Requirement**: Cannot merge if `ci_status != passed`
3. **Approval Requirement**: Cannot merge if `approval_status != approved`
4. **Smoke Test Requirement**: `smoke_test_results` must be non-null for
   `status = approved` (manual verification completed)
5. **Task Completion**: All Refactoring Tasks in `contains` relationship must
   have `status = completed` before PR merge

#### Pull Request: Example Data

```json
{
  "pr_id": "pr-001",
  "pr_number": 42,
  "branch_name": "refactor/ui-py-split",
  "base_branch": "001-codebase-cleanup",
  "title": "Refactor: Split ui.py into route modules",
  "description": "Addresses FR-001 by splitting 3995-line ui.py into 10 focused route modules, each under 300 lines. Maintains backward compatibility via __init__.py re-exports.",
  "file_count": 11,
  "lines_added": 4120,
  "lines_removed": 3995,
  "status": "approved",
  "smoke_test_results": {
    "ui_routes": "passed",
    "backward_compatibility": "passed",
    "manual_endpoint_tests": "passed"
  },
  "ci_status": "passed",
  "approval_status": "approved",
  "approved_by": "reviewer-human",
  "created_at": "2025-12-02T15:00:00Z",
  "updated_at": "2025-12-02T17:30:00Z",
  "merged_at": null,
  "closed_at": null
}
```

---

## Entity Relationship Diagram

```text
┌──────────────┐         contains         ┌────────────────────┐
│ Pull Request │────────────────────────>│ Refactoring Task   │
└──────┬───────┘         (1:N)            └────────┬───────────┘
       │                                           │
       │ modifies (N:M)                            │ targets (N:M)
       │                                           │
       ↓                                           ↓
┌──────────────┐                          ┌──────────────┐
│  Code File   │<─────────────────────────│ Code File    │
└──────┬───────┘                          └──────┬───────┘
       │                                          │
       │ validated_by (1:N)                       │ validated_by (1:N)
       │                                          │
       ↓                                          ↓
┌─────────────────┐                      ┌─────────────────┐
│ Validation Check│                      │ Validation Check│
└─────────────────┘                      └─────────────────┘
       ↑                                          ↑
       │                                          │
       │ triggered_by (N:1)                       │ triggered_by (N:1)
       │                                          │
       └──────────────────────────────────────────┘
                   (from Refactoring Task or PR)


┌────────────────────┐      depends_on      ┌────────────────────┐
│ Refactoring Task A │────────────────────>│ Refactoring Task B │
└────────────────────┘      (N:M)           └────────────────────┘
                            (acyclic)
```

## Cross-Entity Workflows

### Workflow 1: File Assessment to Validation

```text
1. Code File created with status = unassessed
2. Automated scan runs → Validation Check (line_count) created
3. Check fails → Code File.violation_status = violating
4. Refactoring Task created, linked to Code File
5. Task.status = pending → Code File.violation_status = in_progress
6. Task completed → Pull Request created
7. PR triggers CI Validation Checks (Black, ESLint, etc.)
8. All checks pass → PR.ci_status = passed
9. Manual smoke test → Validation Check (smoke_test) created
10. PR merged → Task.status = completed
11. Code File.violation_status = refactored
12. Post-merge validation → Code File.violation_status = validated
```

### Workflow 2: Task Dependency Resolution

```text
1. Task A depends on Task B (Task A.dependencies = [Task B.task_id])
2. Task A.status = blocked
3. Task B.status = in_progress → Task B completes → Task B.status = completed
4. System checks Task A.dependencies[] → all completed
5. Task A.status transitions from blocked → in_progress
6. Task A can now be worked on
```

### Workflow 3: PR Rejection and Rework

```text
1. PR created with status = open
2. CI checks run → ci_status = failed (ESLint error)
3. PR.status = ci_failed
4. Author pushes fix → PR updated
5. CI re-runs → ci_status = passed
6. PR.status = review
7. Reviewer requests changes → approval_status = changes_requested
8. PR.status = rework
9. Author pushes updates → back to ci_pending
10. Cycle repeats until approval_status = approved
11. PR merged → PR.status = merged
```

## Data Integrity Constraints

### Cross-Entity Rules

1. **Task Completion Dependency**: A Refactoring Task cannot have
   `status = completed` if any Code File in `target_files[]` has
   `validation_status != validated`
2. **PR Merge Blocker**: A Pull Request cannot have `status = merged` if:
   - `ci_status != passed`
   - `approval_status != approved`
   - Any contained Refactoring Task has `status != completed`
3. **File State Consistency**: If a Code File has
   `violation_status = validated`, all Validation Checks for that file must have
   `status = passed`
4. **Task Dependency Acyclic Graph**: The `dependencies[]` relationship across
   all Refactoring Tasks must form a Directed Acyclic Graph (DAG)

## Metrics and Reporting

### Key Performance Indicators (KPIs)

| Metric                         | Formula                                                                 | Target    |
| ------------------------------ | ----------------------------------------------------------------------- | --------- |
| **Refactoring Progress**       | (Code Files with `status = validated`) / Total Code Files               | ≥ 80%     |
| **Task Velocity**              | (Tasks with `status = completed`) per week                              | 5-10/week |
| **PR Cycle Time**              | Avg(`merged_at - created_at`) for PRs with `status = merged`            | ≤ 2 days  |
| **Validation Pass Rate**       | (Validation Checks with `status = passed`) / Total Checks               | ≥ 95%     |
| **Deferral Rate**              | (Code Files with `status = deferred`) / Total Code Files                | ≤ 20%     |
| **CI Failure Rate**            | (PRs with `ci_status = failed`) / Total PRs                             | ≤ 10%     |
| **Effort Estimation Accuracy** | Avg(Task.actual_effort / estimated_effort_hours) across completed tasks | 0.8 - 1.2 |

### Sample Query Examples

**Find all critical violations not yet in progress:**

```sql
SELECT * FROM CodeFile
WHERE violation_severity = 'critical'
  AND violation_status IN ('unassessed', 'violating')
ORDER BY refactoring_priority, line_count DESC;
```

**Find blocked tasks ready to unblock:**

```sql
SELECT t.task_id, t.title, t.dependencies
FROM RefactoringTask t
WHERE t.status = 'blocked'
  AND NOT EXISTS (
    SELECT 1 FROM RefactoringTask dep
    WHERE dep.task_id = ANY(t.dependencies)
      AND dep.status NOT IN ('completed', 'deferred')
  );
```

**Calculate PR success rate:**

```sql
SELECT
  (COUNT(*) FILTER (WHERE status = 'merged')) * 100.0 / COUNT(*) AS success_rate,
  AVG(EXTRACT(EPOCH FROM (merged_at - created_at)) / 86400) AS avg_cycle_time_days
FROM PullRequest
WHERE created_at >= NOW() - INTERVAL '30 days';
```

## Implementation Notes

### Storage Recommendations

- **Primary Store**: JSON files in `specs/001-codebase-cleanup/tracking/`
  directory
  - `code-files.json`: Array of Code File entities
  - `tasks.json`: Array of Refactoring Task entities
  - `validation-checks.json`: Array of Validation Check entities
  - `pull-requests.json`: Array of Pull Request entities

- **Alternative**: SQLite database (`tracking.db`) for relational queries and
  reporting

### Automation Integration

- **CI/CD Hooks**: On PR creation/update, trigger Validation Check creation for:
  - `black_formatting`
  - `prettier_formatting`
  - `eslint_validation`
  - `markdownlint_validation`
- **Watchdog Scripts**: Monitor file changes to update `Code File.line_count`
  and re-trigger `line_count` checks
- **Dependency Resolver**: Background job to transition `blocked → in_progress`
  when dependencies resolve

---

**Document Version**: 1.0 **Last Updated**: 2025-12-02 **Maintained By**: Claude
Code Agent
