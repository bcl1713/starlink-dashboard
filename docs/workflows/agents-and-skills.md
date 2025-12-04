# Agents and Skills Reference

This document provides a complete reference for all Claude Code agents and
skills available in this project.

---

## Agents Reference

### Code Quality & Architecture

#### code-architecture-reviewer

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

#### refactor-planner

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

#### plan-reviewer

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

#### documentation-architect

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

#### web-research-specialist

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
