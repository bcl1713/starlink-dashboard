# Skills and Commands Reference

This document provides a complete reference for Claude Code skills and slash
commands.

---

## Slash Commands

Slash commands are quick shortcuts for common workflows. Type them directly in
the chat.

### /dev-docs [description]

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

1. **`[task-name]-plan.md`** - Comprehensive plan with:
   - Executive Summary
   - Current State Analysis
   - Proposed Future State
   - Implementation Phases
   - Detailed Tasks with acceptance criteria
   - Risk Assessment
   - Success Metrics
   - Timeline Estimates

2. **`[task-name]-context.md`** - Key context including:
   - Relevant files and their purposes
   - Architectural decisions
   - Dependencies
   - Integration points

3. **`[task-name]-tasks.md`** - Checklist format for tracking:
   - Numbered, prioritized tasks
   - Clear acceptance criteria
   - Dependency mapping
   - Progress tracking

**Example for this project:**

```text
/dev-docs Add predictive satellite position forecasting

This will analyze your current position tracking code, design a
forecasting system, and create a complete implementation plan with tasks.
```

**Best Practice:** Use this AFTER exiting plan mode when you have a clear
vision. The files persist across context resets, so you can pick up where you
left off.

---

### /dev-docs-update [optional context]

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
/dev-docs-update Completed Prometheus metrics refactor, added 5 new metrics
```

**Best Practice:** Run this before ending a session so the next Claude instance
(or you later) can pick up seamlessly.

---

## Skills System

Skills are context-aware guidelines that automatically activate based on what
you're working on.

### Currently Installed Skills

#### skill-developer

**Purpose:** Meta-skill for creating and managing Claude Code skills.

**Auto-activates when:**

- Editing `.claude/skills/` files
- Discussing skill triggers, rules, or hooks
- Keywords: "skill system", "create skill", "skill triggers"

**Use when:** Building custom skills for your project.

---

#### grafana-dashboard

**Purpose:** Guidelines for creating and editing Grafana dashboards with
Prometheus queries.

**Auto-activates when:**

- Editing files in `monitoring/grafana/provisioning/dashboards/`
- Keywords: "grafana", "dashboard", "panel", "promql", "geomap"
- Discussing Prometheus queries or visualizations

**Use when:**

- Creating new Grafana panels
- Writing Prometheus queries
- Configuring dashboard JSON
- Adding new visualizations

**Example triggers:**

```text
"Add a new timeseries panel for signal strength"
"How do I write a PromQL query for average latency?"
"Create a geomap panel showing satellite position"
```

---

### How Skills Work

**Automatic Activation:**

The `skill-activation-prompt` hook monitors your prompts and file edits. When it
detects relevant keywords or file patterns, it suggests the appropriate skill.

**Manual Activation:**

You can explicitly request a skill:

```text
"Use the grafana-dashboard skill to help me create a new panel"
```

**Skill Suggestion:**

When a skill is suggested but not automatically loaded, you can accept or
decline:

- Accept: "Yes, use that skill"
- Decline: Continue without it

---

## File Locations

```text
.claude/
├── commands/                  # Slash commands
│   ├── dev-docs.md
│   └── dev-docs-update.md
├── skills/                    # Skills and rules
│   ├── grafana-dashboard/
│   ├── skill-developer/
│   └── skill-rules.json
├── hooks/                     # Automation hooks
│   ├── skill-activation-prompt.sh
│   └── post-tool-use-tracker.sh
└── settings.json              # Project settings

dev/
└── active/                    # Active development tasks
    └── [task-name]/
        ├── [task-name]-plan.md
        ├── [task-name]-context.md
        └── [task-name]-tasks.md
```
