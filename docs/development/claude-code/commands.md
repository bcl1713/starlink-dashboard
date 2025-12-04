# Slash Commands Reference

Quick commands you can type in chat to trigger specific workflows.

[Back to main guide →](./README.md)

---

## `/dev-docs [description]`

**Purpose:** Creates a comprehensive strategic plan with structured task
breakdown.

**When to use:**

- Starting a new feature
- Planning a major refactor
- Need a detailed implementation roadmap
- Want to break down complex work into tasks

**Syntax:**

```text
/dev-docs Add historical data export feature
/dev-docs Implement real-time alerting system
/dev-docs Refactor metrics collection for better performance
```

**What it creates:**

Creates a directory structure in `dev/active/[task-name]/` with three files:

### 1. `[task-name]-plan.md`

Comprehensive plan with:

- Executive Summary
- Current State Analysis
- Proposed Future State
- Implementation Phases
- Detailed Tasks with acceptance criteria
- Risk Assessment
- Success Metrics
- Timeline Estimates

### 2. `[task-name]-context.md`

Key context including:

- Relevant files and their purposes
- Architectural decisions
- Dependencies
- Integration points

### 3. `[task-name]-tasks.md`

Checklist format for tracking:

- Numbered, prioritized tasks
- Clear acceptance criteria
- Dependency mapping
- Progress tracking (✅/⏳/🔲)

**Example for this project:**

```text
/dev-docs Add predictive satellite position forecasting

This will analyze your current position tracking code, design a
forecasting system, and create a complete implementation plan with
tasks.
```

**Best Practice:** Use this AFTER exiting plan mode when you have a clear
vision. The files persist across context resets, so you can pick up where you
left off.

---

## `/dev-docs-update [optional context]`

**Purpose:** Updates development documentation before context compaction or when
switching conversations.

**When to use:**

- Approaching context limits
- Before taking a break from work
- After completing significant work
- Before switching to a new conversation

**Syntax:**

```text
/dev-docs-update
/dev-docs-update Focus on the alerting system implementation
/dev-docs-update Just finished metrics refactor
```

**What it updates:**

1. **Active task context files** - Current state, decisions made, blockers
2. **Task checklists** - Mark completed items, add new tasks
3. **Session context** - Complex problems solved, architectural decisions
4. **Handoff notes** - Exact state for continuing work later

**Example for this project:**

```text
# When approaching context limit:
/dev-docs-update

# When documenting specific work:
/dev-docs-update Completed Prometheus metrics refactor, added 5 new
metrics
```

**Best Practice:** Run this before ending a session so the next Claude instance
(or you later) can pick up seamlessly.

---

## Command Workflow Patterns

### Starting New Work

```text
/dev-docs [description]
→ Creates plan structure
```

### Before Context Reset

```text
/dev-docs-update
→ Preserves all progress
```

### Common Sequence

1. Plan work: `/dev-docs Add new feature`
2. Do implementation work
3. Update before stopping: `/dev-docs-update [what you accomplished]`

---

## Tips for Effective Usage

### Descriptive Titles

Good:

```text
/dev-docs Add real-time position streaming with WebSocket support
```

Not as helpful:

```text
/dev-docs Add streaming
```

### Include Context

Good:

```text
/dev-docs-update Completed phase 1: basic metric collection, now
working on Prometheus exporter integration
```

Not as helpful:

```text
/dev-docs-update Finished some stuff
```

### Update Regularly

- After completing major tasks
- When you discover new requirements
- Before ending your session
- When switching between features
