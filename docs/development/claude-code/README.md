# Claude Code Workflows Guide

**Last Updated:** 2025-10-30

This guide explains how to use Claude Code agents, commands, and skills
installed in this project to enhance your development workflow.

---

## Quick Start

This project uses Claude Code's advanced infrastructure to provide specialized
AI assistance for common development tasks. The system consists of three main
components:

### **Agents**

Specialized AI assistants that handle complex, multi-step tasks autonomously.
Think of them as expert teammates you can call on for specific jobs.

**Common use cases:**

- Code review and architecture feedback
- Creating refactoring plans
- Comprehensive documentation
- Technical research
- Development planning

[Learn about all agents →](./agents.md)

### **Slash Commands**

Quick commands you type in chat to trigger specific workflows (e.g.,
`/dev-docs`, `/dev-docs-update`).

**Common use cases:**

- Planning new features
- Updating task documentation
- Creating comprehensive development plans

[Learn about slash commands →](./commands.md)

### **Skills**

Context-aware guidelines that automatically activate when working on specific
files or topics (e.g., `grafana-dashboard` skill activates when working with
Grafana configs).

**Currently installed skills:**

- `grafana-dashboard` - For Grafana dashboard creation
- `skill-developer` - For creating Claude Code skills

[Learn about the skills system →](./skills.md)

---

## Common Workflows

### Adding a New Prometheus Metric

1. Plan: `/dev-docs Add [metric name] to Prometheus`
2. Implement in `backend/starlink-location/app/api/metrics.py`
3. Review: "Review the new [metric name] metric I just added"
4. Document: Update `docs/METRICS.md`
5. Update progress: `/dev-docs-update Completed [metric name]`

### Refactoring Existing Code

1. Plan: "Create a refactoring plan for `[path/to/code]`"
2. Review plan: "Review this refactoring plan before I start"
3. Execute incrementally
4. Review: "Review the [system] refactoring I just completed"
5. Update: `/dev-docs-update Completed [system] refactoring`

### Debugging Complex Issues

1. Research: "Research [common causes of the problem]"
2. Plan: `/dev-docs Debug and fix [issue]`
3. Document findings as you debug
4. Review fix: "Review my fix for [issue]"
5. Update: `/dev-docs-update Fixed [issue]`

---

## Quick Reference

### Agent Quick Lookup

| Need...                     | Use...                       |
| --------------------------- | ---------------------------- |
| Code architecture feedback  | `code-architecture-reviewer` |
| Comprehensive documentation | `documentation-architect`    |
| Refactoring planning        | `refactor-planner`           |
| Plan validation             | `plan-reviewer`              |
| External research/solutions | `web-research-specialist`    |

### Slash Commands

| Command            | Purpose                              |
| ------------------ | ------------------------------------ |
| `/dev-docs [desc]` | Create comprehensive plan with tasks |
| `/dev-docs-update` | Update docs before context reset     |

### Key File Locations

```text
.claude/
├── agents/                      # Agent definitions
├── commands/                    # Slash commands
├── skills/                      # Skills and rules
└── hooks/                       # Automation hooks

dev/active/                      # Active development tasks
└── [task-name]/
    ├── [task-name]-plan.md
    ├── [task-name]-context.md
    └── [task-name]-tasks.md
```

---

## Best Practices

### When to Use Agents vs. Direct Questions

**Use agents when:**

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

1. Start with `/dev-docs` for big features
2. Use `plan-reviewer` to validate plans
3. Update with `/dev-docs-update` regularly
4. Review with `code-architecture-reviewer` after implementation

### Documentation Workflow

1. Create docs as you go
2. Use `documentation-architect` for comprehensive docs
3. Update existing docs when adding features
4. Document "why" decisions in context files

### Code Quality Workflow

1. Plan refactoring with `refactor-planner`
2. Make incremental changes
3. Review each phase with `code-architecture-reviewer`
4. Test thoroughly after refactoring

---

## Learn More

- [Agents Reference](./agents.md) - Detailed guide to all available agents
- [Slash Commands](./commands.md) - Complete command reference
- [Skills System](./skills.md) - How skills work and current installations
- [Practical Examples](./examples.md) - Real-world workflows for this project

## Getting Help

**For Claude Code itself:**

- Documentation: [Claude Code docs](https://docs.claude.com/en/docs/claude-code)
- Issues: [GitHub issues](https://github.com/anthropics/claude-code/issues)

**For this project:**

- Ask Claude: "How do I [task]?"
- Check existing docs in `docs/`
- Review `.claude/` infrastructure

Remember: These tools are here to help you work more efficiently. Don't hesitate
to experiment and find workflows that work best for you!
