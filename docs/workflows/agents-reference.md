# Agents Reference

This document provides a complete reference for all Claude Code agents available
in this project.

---

## Code Quality & Architecture

### code-architecture-reviewer

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

### refactor-planner

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

## Development Planning

### plan-reviewer

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

## Documentation

### documentation-architect

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

## Research & Debugging

### web-research-specialist

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

## File Locations

```text
.claude/
├── agents/                    # Agent definitions
│   ├── code-architecture-reviewer.md
│   ├── documentation-architect.md
│   ├── refactor-planner.md
│   ├── plan-reviewer.md
│   └── web-research-specialist.md
```
