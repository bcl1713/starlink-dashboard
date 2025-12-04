# Claude Code Workflows Guide

**Last Updated:** 2025-10-30

This guide explains how to use the Claude Code agents, commands, and skills
installed in this project to enhance your development workflow.

---

## Table of Contents

1. [Overview](#overview)
2. [Agents Reference](#agents-reference)
3. [Slash Commands](#slash-commands)
4. [Skills System](#skills-system)
5. [Practical Workflows](#practical-workflows)
6. [Best Practices](#best-practices)
7. [Quick Reference](#quick-reference)

---

## Overview

This project uses Claude Code's advanced infrastructure to provide specialized
AI assistance for common development tasks. The system consists of three main
components:

### **Agents**

Specialized AI assistants that handle complex, multi-step tasks autonomously.
Think of them as expert teammates you can call on for specific jobs.

### **Slash Commands**

Quick commands you type in chat to trigger specific workflows (e.g.,
`/dev-docs`, `/dev-docs-update`).

### **Skills**

Context-aware guidelines that automatically activate when working on specific
files or topics (e.g., `grafana-dashboard` skill activates when working with
Grafana configs).

---

## Agents Reference

### Code Quality & Architecture

#### `code-architecture-reviewer`

**Purpose:** Reviews code for architectural consistency, best practices, and
integration with existing systems.

**When to use:**

- After implementing a new feature
- After refactoring existing code
- Before creating a pull request
- When you want a second opinion on implementation

**How to invoke:**

```text
"Review the metrics export implementation"
"Check if the new simulation logic follows best practices"
"Review backend/starlink-location/app/api/metrics.py"
```

**What it does:**

1. Examines your code thoroughly
2. Questions implementation decisions
3. Checks for consistency with project patterns
4. Identifies potential issues or improvements
5. Provides detailed feedback

**Example for this project:**

```text
"I just added a new Prometheus metric for satellite signal strength.
Can you review it?"
```

---

#### `refactor-planner`

**Purpose:** Analyzes existing code and creates comprehensive refactoring plans
with risk assessment.

**When to use:**

- Code is becoming hard to maintain
- You notice code duplication
- You want to modernize legacy patterns
- Before major restructuring

**How to invoke:**

```text
"Create a refactoring plan for the metrics exporters"
"Analyze the simulation code and suggest improvements"
"Plan refactoring for backend/starlink-location/app/core/"
```

**What it does:**

1. Analyzes current code structure
2. Identifies improvement opportunities
3. Creates step-by-step refactoring plan
4. Assesses risks and dependencies
5. Estimates effort and impact

**Example for this project:**

```text
"The metrics collection code is getting messy with all the new
satellite data. Can you create a refactoring plan?"
```

---

### Development Planning

#### `plan-reviewer`

**Purpose:** Reviews development plans before implementation to catch issues
early.

**When to use:**

- Before starting major features
- Before architectural changes
- When planning complex integrations
- To validate your approach

**How to invoke:**

```text
"Review this plan: [paste your plan]"
"I'm planning to add real-time alerting. Can you review my approach?"
```

**What it does:**

1. Analyzes the plan for completeness
2. Identifies missing considerations
3. Suggests alternative approaches
4. Highlights potential risks
5. Provides improvement recommendations

**Example for this project:**

```text
"I plan to add a feature that alerts when signal quality drops below
threshold. Here's my plan: [details]. Can you review it?"
```

---

### Documentation

#### `documentation-architect`

**Purpose:** Creates comprehensive documentation by gathering context from code,
existing docs, and project knowledge.

**When to use:**

- Need API documentation
- Creating architecture overviews
- Documenting data flows
- Updating outdated docs
- Explaining complex systems

**How to invoke:**

```text
"Document the Prometheus metrics architecture"
"Create API documentation for the health check endpoints"
"Document how the simulation mode works"
"Create a data flow diagram for metrics collection"
```

**What it does:**

1. Gathers context from code and existing documentation
2. Analyzes system architecture
3. Creates comprehensive, well-structured documentation
4. Includes diagrams and examples where helpful
5. Ensures accuracy and completeness

**Example for this project:**

```text
"Create comprehensive documentation for all the Prometheus metrics
we expose, including what they measure and when to use them"
```

---

### Research & Debugging

#### `web-research-specialist`

**Purpose:** Researches technical problems across GitHub issues, Stack Overflow,
Reddit, forums, and other community resources.

**When to use:**

- Debugging tricky issues
- Finding best practices
- Comparing different approaches
- Looking for known issues with libraries
- Researching implementation patterns

**How to invoke:**

```text
"Research best practices for Prometheus metric naming"
"Find solutions for FastAPI + Prometheus integration issues"
"Research how others handle Grafana dashboard provisioning"
"Look up common issues with grpcio and Python 3.11"
```

**What it does:**

1. Searches multiple sources (GitHub, Stack Overflow, Reddit, etc.)
2. Compiles findings from relevant discussions
3. Identifies common solutions and patterns
4. Provides links to detailed resources
5. Summarizes recommendations

**Example for this project:**

```text
"I'm seeing inconsistent Prometheus scrape intervals. Research
common causes and solutions."
```

---

## Slash Commands

Slash commands are quick shortcuts for common workflows. Type them directly in
the chat.

### `/dev-docs [description]`

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

**What it creates:** Creates a directory structure in `dev/active/[task-name]/`
with three files:

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
   - Progress tracking (✅/⏳/🔲)

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

### `/dev-docs-update [optional context]`

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

#### `skill-developer`

**Purpose:** Meta-skill for creating and managing Claude Code skills.

**Auto-activates when:**

- Editing `.claude/skills/` files
- Discussing skill triggers, rules, or hooks
- Keywords: "skill system", "create skill", "skill triggers"

**Use when:** Building custom skills for your project.

---

#### `grafana-dashboard`

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

**Automatic Activation:** The `skill-activation-prompt` hook monitors your
prompts and file edits. When it detects relevant keywords or file patterns, it
suggests the appropriate skill.

**Manual Activation:** You can explicitly request a skill:

```text
"Use the grafana-dashboard skill to help me create a new panel"
```

**Skill Suggestion:** When a skill is suggested but not automatically loaded,
you can accept or decline:

- Accept: "Yes, use that skill"
- Decline: Continue without it

---

## Practical Workflows

Here are complete workflows for common tasks in this project.

### Workflow 1: Adding a New Prometheus Metric

**Scenario:** You want to add a new metric for satellite signal quality.

**Steps:**

1. **Plan the implementation:**

```text
   /dev-docs Add satellite signal quality metric to Prometheus
```

This creates a detailed plan in `dev/active/signal-quality-metric/`

1. **Implement the metric:** Edit `backend/starlink-location/app/api/metrics.py`
   and add your metric code.

1. **Review the implementation:**

```text
   "Review the new signal quality metric I just added"
```

The `code-architecture-reviewer` agent examines your code.

1. **Document the metric:**

```text
   "Update docs/METRICS.md to include the new signal quality metric"
```

Or use the `documentation-architect` agent for comprehensive docs.

1. **Update task tracking:**

```text
   /dev-docs-update Completed signal quality metric implementation
```

---

### Workflow 2: Creating a New Grafana Dashboard

**Scenario:** You want to create a new dashboard for satellite health
monitoring.

**Steps:**

1. **Research best practices:**

```text
   "Research best practices for Grafana satellite monitoring dashboards"
```

The `web-research-specialist` agent finds examples and patterns.

1. **Plan the dashboard:**

```text
   /dev-docs Create satellite health monitoring dashboard
```

1. **Create the dashboard JSON:** Edit a file in
   `monitoring/grafana/provisioning/dashboards/`

   The `grafana-dashboard` skill auto-activates and provides guidance.

1. **Test the dashboard:** Load it in Grafana at <http://localhost:3000>

1. **Document the dashboard:**

```text
   "Add documentation for the satellite health dashboard to docs/grafana-setup.md"
```

---

### Workflow 3: Refactoring Existing Code

**Scenario:** The metrics collection code is getting messy and needs
refactoring.

**Steps:**

1. **Create a refactoring plan:**

```text
   "Create a refactoring plan for backend/starlink-location/app/api/metrics.py"
```

The `refactor-planner` agent analyzes the code and creates a detailed plan.

1. **Review the plan:**

```text
   "Review this refactoring plan before I start implementation"
```

The `plan-reviewer` agent validates the approach.

1. **Execute the refactoring:** Follow the plan step-by-step, making changes
   incrementally.

1. **Review each significant change:**

```text
   "Review the metrics collector refactoring I just completed"
```

1. **Update documentation:**

```text
   /dev-docs-update Completed metrics collector refactoring
```

---

### Workflow 4: Debugging a Complex Issue

**Scenario:** Prometheus scrapes are timing out intermittently.

**Steps:**

1. **Research the problem:**

```text
   "Research common causes of Prometheus scrape timeouts with FastAPI"
```

The `web-research-specialist` agent searches for solutions.

1. **Create a debugging plan:**

```text
   /dev-docs Debug and fix Prometheus scrape timeout issues
```

1. **Document findings as you debug:** Keep notes in
   `dev/active/scrape-timeout-debug/[task]-context.md`

1. **Review the fix:**

```text
   "Review my fix for the Prometheus timeout issue"
```

1. **Document the solution:**

```text
   "Add this to troubleshooting docs so we don't hit this again"
```

1. **Update task tracking:**

```text
   /dev-docs-update Fixed Prometheus timeout by optimizing metrics calculation
```

---

### Workflow 5: Adding a Major New Feature

**Scenario:** You want to add real-time alerting when satellite signal drops
below a threshold.

**Steps:**

1. **Create comprehensive plan:**

```text
   /dev-docs Implement real-time alerting system for satellite signal quality
```

1. **Review the plan before starting:**

```text
   "Review the alerting system plan"
```

The `plan-reviewer` agent validates the approach.

1. **Research implementation patterns:**

```text
   "Research best practices for implementing alerting with Prometheus and Grafana"
```

1. **Implement in phases:** Follow the tasks in
   `dev/active/alerting-system/alerting-system-tasks.md`

   After each phase:

```text
   "Review the alert rule configuration I just added"
```

1. **Document the system:**

```text
   "Create comprehensive documentation for the alerting system"
```

The `documentation-architect` agent creates detailed docs.

1. **Update progress regularly:**

```text
   /dev-docs-update Completed phase 1 of alerting system (alert rules)
```

---

## Best Practices

### When to Use Agents vs. Direct Questions

**Use Agents when:**

- Task is complex and multi-step
- Need thorough analysis or research
- Want comprehensive documentation
- Planning significant work
- Reviewing completed work

**Ask directly when:**

- Quick questions
- Simple code changes
- Clarification needed
- Immediate fixes

### Planning Workflow

1. **Start with `/dev-docs`** for big features - creates persistent structure
2. **Use `plan-reviewer`** to validate plans before coding
3. **Update with `/dev-docs-update`** regularly to preserve context
4. **Review with `code-architecture-reviewer`** after implementation

### Documentation Workflow

1. **Create docs as you go** - Don't wait until the end
2. **Use `documentation-architect`** for comprehensive docs
3. **Update existing docs** when adding features
4. **Document "why" decisions** in `-context.md` files

### Code Quality Workflow

1. **Plan refactoring** with `refactor-planner` before making changes
2. **Make incremental changes** - don't refactor everything at once
3. **Review each phase** with `code-architecture-reviewer`
4. **Test thoroughly** after refactoring

### Research Workflow

1. **Start with `web-research-specialist`** for external knowledge
2. **Validate findings** against your specific use case
3. **Document patterns** you adopt in project docs
4. **Share knowledge** in `-context.md` files for future reference

---

## Quick Reference

### Agent Invocation Patterns

| Agent                        | Invoke With                          |
| ---------------------------- | ------------------------------------ |
| `code-architecture-reviewer` | "Review [file/feature]"              |
| `documentation-architect`    | "Document [system/API/feature]"      |
| `refactor-planner`           | "Create refactoring plan for [code]" |
| `plan-reviewer`              | "Review this plan: [plan]"           |
| `web-research-specialist`    | "Research [topic/problem]"           |

### Quick Reference - Slash Commands

| Command                      | Purpose                                       |
| ---------------------------- | --------------------------------------------- |
| `/dev-docs [description]`    | Create comprehensive plan with task structure |
| `/dev-docs-update [context]` | Update docs before context reset              |

### Skills

| Skill               | Auto-Activates On                                     |
| ------------------- | ----------------------------------------------------- |
| `grafana-dashboard` | Editing `monitoring/grafana/` files, Grafana keywords |
| `skill-developer`   | Editing `.claude/skills/`, skill-related keywords     |

### File Locations

```text
.claude/
├── agents/                    # Agent definitions
│   ├── code-architecture-reviewer.md
│   ├── documentation-architect.md
│   ├── refactor-planner.md
│   ├── plan-reviewer.md
│   └── web-research-specialist.md
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

### Common Patterns

**Starting new work:**

```text
/dev-docs [description]
→ Creates plan structure
```

**Before context reset:**

```text
/dev-docs-update
→ Preserves all progress
```

**After implementing:**

```text
"Review [what I just built]"
→ Gets architectural feedback
```

**When stuck:**

```text
"Research [the problem]"
→ Finds solutions from community
```

**Need comprehensive docs:**

```text
"Document [system/feature]"
→ Creates detailed documentation
```

---

## Tips for This Project

### Prometheus Metrics

When adding new metrics, always:

1. Use `web-research-specialist` to verify naming conventions
2. Document in `docs/METRICS.md`
3. Test scraping with `curl <http://localhost:8000/metrics`>
4. Review with `code-architecture-reviewer`

### Grafana Dashboards

When creating dashboards:

1. The `grafana-dashboard` skill auto-activates - use its guidance
2. Test queries in Grafana's query builder first
3. Export JSON and commit to `monitoring/grafana/provisioning/dashboards/`
4. Document in `docs/grafana-setup.md`

### Backend Development

When modifying backend code:

1. Simulation mode makes testing easier - use it!
2. Check health endpoint: `curl <http://localhost:8000/health`>
3. Review FastAPI docs for async patterns
4. Use type hints consistently

### Development Task Management

Use the `dev/active/` directory for all major work:

- Persists across context resets
- Provides clear handoff documentation
- Tracks progress with checklists
- Captures important decisions

---

## Getting Help

**For Claude Code itself:**

- Documentation: <https://docs.claude.com/en/docs/claude-code>
- Issues: <https://github.com/anthropics/claude-code/issues>

**For this project:**

- Ask Claude: "How do I [task]?"
- Check existing docs in `docs/`
- Review `.claude/` infrastructure

**Remember:** These tools are here to help you work more efficiently. Don't
hesitate to experiment and find workflows that work best for you!
