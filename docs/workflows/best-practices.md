# Best Practices

This document provides guidelines and recommendations for effective development
using Claude Code workflows.

---

## When to Use Agents vs. Direct Questions

### Use Agents when

- Task is complex and multi-step
- Need thorough analysis or research
- Want comprehensive documentation
- Planning significant work
- Reviewing completed work

### Ask directly when

- Quick questions
- Simple code changes
- Clarification needed
- Immediate fixes

---

## Planning Workflow

1. **Start with `/dev-docs`** for big features - creates persistent structure
2. **Use `plan-reviewer`** to validate plans before coding
3. **Update with `/dev-docs-update`** regularly to preserve context
4. **Review with `code-architecture-reviewer`** after implementation

---

## Documentation Workflow

1. **Create docs as you go** - Don't wait until the end
2. **Use `documentation-architect`** for comprehensive docs
3. **Update existing docs** when adding features
4. **Document "why" decisions** in `-context.md` files

---

## Code Quality Workflow

1. **Plan refactoring** with `refactor-planner` before making changes
2. **Make incremental changes** - don't refactor everything at once
3. **Review each phase** with `code-architecture-reviewer`
4. **Test thoroughly** after refactoring

---

## Research Workflow

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

### Slash Commands

| Command                      | Purpose                                       |
| ---------------------------- | --------------------------------------------- |
| `/dev-docs [description]`    | Create comprehensive plan with task structure |
| `/dev-docs-update [context]` | Update docs before context reset              |

### Skills

| Skill               | Auto-Activates On                                     |
| ------------------- | ----------------------------------------------------- |
| `grafana-dashboard` | Editing `monitoring/grafana/` files, Grafana keywords |
| `skill-developer`   | Editing `.claude/skills/`, skill-related keywords     |

---

## Common Patterns

### Starting New Work

```text
/dev-docs [description]
```

Creates plan structure

### Before Context Reset

```text
/dev-docs-update
```

Preserves all progress

### After Implementing

```text
"Review [what I just built]"
```

Gets architectural feedback

### When Stuck

```text
"Research [the problem]"
```

Finds solutions from community

### Need Comprehensive Docs

```text
"Document [system/feature]"
```

Creates detailed documentation
