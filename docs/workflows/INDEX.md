# Claude Code Workflows Guide

**Last Updated:** 2025-10-30

This guide explains how to use the Claude Code agents, commands, and skills
installed in this project to enhance your development workflow.

---

## Overview

This project uses Claude Code's advanced infrastructure to provide specialized AI
assistance for common development tasks. The system consists of three main
components:

### Agents

Specialized AI assistants that handle complex, multi-step tasks autonomously.
Think of them as expert teammates you can call on for specific jobs.

### Slash Commands

Quick commands you type in chat to trigger specific workflows (e.g., `/dev-docs`,
`/dev-docs-update`).

### Skills

Context-aware guidelines that automatically activate when working on specific
files or topics (e.g., `grafana-dashboard` skill activates when working with
Grafana configs).

---

## Documentation Contents

This guide is organized into the following sections:

### [Agents and Skills Reference](agents-and-skills.md)

Complete reference for all available agents and skills:

- **Code Quality & Architecture** - `code-architecture-reviewer`,
  `refactor-planner`
- **Development Planning** - `plan-reviewer`
- **Documentation** - `documentation-architect`
- **Research & Debugging** - `web-research-specialist`
- **Skills System** - `grafana-dashboard`, `skill-developer`

### [Practical Workflows](practical-workflows.md)

Step-by-step workflows for common development tasks:

- Adding a new Prometheus metric
- Creating a new Grafana dashboard
- Refactoring existing code
- Debugging complex issues
- Adding major new features

### [Best Practices](best-practices.md)

Guidelines and recommendations for effective development:

- When to use agents vs. direct questions
- Planning workflow
- Documentation workflow
- Code quality workflow
- Research workflow
- Quick reference tables and common patterns

---

## Quick Start

### Starting New Work

```text
/dev-docs [description]
```

Creates a comprehensive plan with task structure in `dev/active/[task-name]/`

### Before Context Reset

```text
/dev-docs-update
```

Preserves all progress and captures current state

### After Implementing

```text
"Review [what I just built]"
```

Gets architectural feedback from `code-architecture-reviewer`

### When Stuck

```text
"Research [the problem]"
```

Finds solutions from community via `web-research-specialist`

### Need Comprehensive Docs

```text
"Document [system/feature]"
```

Creates detailed documentation via `documentation-architect`

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
