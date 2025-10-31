# Development Directory

**Last Updated:** 2025-10-30

This directory contains all active development planning, task tracking, and session notes.

---

## Quick Navigation

- **[STATUS.md](./STATUS.md)** - Current development status and active tasks
- **[active/](./active/)** - Active task folders with planning documents

---

## Directory Structure

```
dev/
├── STATUS.md                    # Current project status
├── README.md                    # This file
└── active/                      # Active development tasks
    └── poi-interactive-management/
        ├── README.md                              # Quick reference
        ├── SESSION-NOTES.md                       # Latest session details ⭐
        ├── RESEARCH-SUMMARY.md                    # Best practices summary
        ├── poi-interactive-management-plan.md     # Strategic plan (27 KB)
        ├── poi-interactive-management-context.md  # Implementation context
        ├── poi-interactive-management-tasks.md    # Task checklist (47 tasks)
        └── poi-best-practices-research.md         # Full research (75 KB)
```

---

## How to Use This Directory

### Starting a New Task

1. Create folder in `active/`: `mkdir active/[task-name]/`
2. Run planning slash command: `/dev-docs "task description"`
3. This generates:
   - `[task-name]-plan.md` - Strategic plan
   - `[task-name]-context.md` - Implementation context
   - `[task-name]-tasks.md` - Task checklist
   - `README.md` - Quick reference

### Working on an Active Task

1. Read `SESSION-NOTES.md` for latest state
2. Open `[task-name]-tasks.md` for checklist
3. Reference `[task-name]-context.md` for patterns
4. Update checklist as you complete tasks
5. Update `SESSION-NOTES.md` at end of session

### After Context Reset

1. Read `/dev/STATUS.md` for project overview
2. Check `active/[task-name]/SESSION-NOTES.md` for latest
3. Review task checklist for current progress
4. Continue from "Next Steps" in session notes

### Completing a Task

1. Ensure all tasks marked complete ✅
2. Commit all code changes
3. Update `/dev/STATUS.md` to reflect completion
4. Archive task folder to `completed/` (optional)

---

## File Naming Conventions

### Task Folders
- Use lowercase with hyphens: `poi-interactive-management`
- Be descriptive but concise: `user-auth-system`

### Documentation Files
- Plan: `[task-name]-plan.md` (strategic overview)
- Context: `[task-name]-context.md` (implementation details)
- Tasks: `[task-name]-tasks.md` (checklist with acceptance criteria)
- Session: `SESSION-NOTES.md` (latest session information)
- Research: `[topic]-research.md` or `RESEARCH-SUMMARY.md`

---

## Task Lifecycle

```
1. PLANNING
   ├─ Create task folder
   ├─ Research best practices
   ├─ Write strategic plan
   ├─ Define task checklist
   └─ Document architecture decisions

2. IMPLEMENTATION
   ├─ Create feature branch
   ├─ Work through task checklist
   ├─ Update session notes regularly
   ├─ Test against acceptance criteria
   └─ Document issues/blockers

3. REVIEW
   ├─ Self-review all changes
   ├─ Update documentation
   ├─ Verify all tests pass
   └─ Create pull request

4. COMPLETE
   ├─ Merge to dev branch
   ├─ Update project status
   ├─ Archive task folder (optional)
   └─ Celebrate! 🎉
```

---

## Current Active Tasks

See [STATUS.md](./STATUS.md) for current status.

**Active:** POI Interactive Management (Planning Complete)

---

## Best Practices

### Documentation
- ✅ Update session notes at end of each session
- ✅ Keep task checklist current (mark completed ✅)
- ✅ Document critical decisions in context file
- ✅ Add troubleshooting notes as you discover issues

### Code Organization
- ✅ Reference files with line numbers: `file.py:123`
- ✅ Document "why" not just "what"
- ✅ Include code examples in context docs
- ✅ Add acceptance criteria to each task

### Context Management
- ✅ Use session notes for continuity across resets
- ✅ Capture patterns and solutions, not just code
- ✅ Document blockers and workarounds
- ✅ Write handoff notes before context limit

---

## Templates

### New Task README Template
```markdown
# [Task Name]

**Status:** Planning / Implementation / Testing / Complete
**Feature Branch:** feature/[task-name]
**Created:** YYYY-MM-DD

## Overview
Brief description of the task.

## Key Documents
- [Plan](./[task-name]-plan.md)
- [Context](./[task-name]-context.md)
- [Tasks](./[task-name]-tasks.md)
- [Session Notes](./SESSION-NOTES.md)

## Quick Start
Steps to begin working on this task.

## Success Criteria
How to know when task is complete.
```

### Session Notes Template
```markdown
# [Task Name] - Session Notes

**Last Updated:** YYYY-MM-DD
**Session Type:** Planning / Implementation / Testing
**Status:** In Progress / Blocked / Complete

## What Was Accomplished
- List of accomplishments

## Current State
- Files modified
- Code written
- Tests added

## Next Immediate Steps
1. Specific next action
2. Second action
...

## Blockers & Risks
- Any issues encountered

## Handoff Notes
Critical information for next session.
```

---

## Maintenance

### Weekly
- Review active tasks for progress
- Update STATUS.md
- Archive completed tasks

### Monthly
- Review technical debt
- Update best practices based on learnings
- Clean up old session notes (keep latest)

### Per Release
- Document all changes in project changelog
- Update main README
- Archive planning documents

---

## Tips for Working with Claude Code

### Effective Context Management
- Use session notes to maintain continuity
- Reference specific file paths and line numbers
- Break large tasks into smaller subtasks
- Update documentation as you go

### Before Context Reset
- Save all important state to session notes
- Document exact files and lines being edited
- Write clear handoff notes for next session
- Commit code or clearly mark uncommitted changes

### After Context Reset
- Start by reading session notes
- Verify environment state with test commands
- Review task checklist for context
- Ask questions if anything is unclear

---

## Related Documentation

### Project Documentation
- [Main README](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - Instructions for Claude Code
- [Design Document](../docs/design-document.md) - System architecture
- [Development Plan](../docs/phased-development-plan.md) - Original plan

### Active Task Documentation
- [POI Management](./active/poi-interactive-management/) - Current task

---

## Questions?

For questions about:
- **Task structure:** See templates above
- **Current status:** Check STATUS.md
- **Active work:** Read SESSION-NOTES.md in task folder
- **Architecture:** See project design document

---

**Last Updated:** 2025-10-30
