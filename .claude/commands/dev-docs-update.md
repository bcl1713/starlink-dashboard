---
description: Update dev documentation before context compaction
argument-hint: Optional - specific context or tasks to focus on (leave empty for comprehensive update)
---

We're approaching context limits. Please update the development documentation to ensure seamless continuation after context reset.

## File Naming Standards

When creating session files, use ALL CAPS with hyphens:
- `SESSION-NOTES.md` (NOT `session_notes.md` or `SESSION_NOTES.md`)

Follow `.claude/NAMING-CONVENTIONS.md` for all file creation.

**Important:** All handoff information goes in `SESSION-NOTES.md` and `STATUS.md` ONLY. No separate CONTEXT-HANDOFF or PHASE-N-SUMMARY documents.

## Required Updates

### 1. Update Active Task Documentation
For each task in `/dev/active/`:
- Update `[task-name]-context.md` with:
  - Current implementation state
  - Key decisions made this session
  - Files modified and why
  - Any blockers or issues discovered
  - Next immediate steps
  - Last Updated timestamp

- Update `[task-name]-tasks.md` with:
  - Mark completed tasks as ✅ 
  - Add any new tasks discovered
  - Update in-progress tasks with current status
  - Reorder priorities if needed

### 2. Capture Session Context
Include any relevant information about:
- Complex problems solved
- Architectural decisions made
- Tricky bugs found and fixed
- Integration points discovered
- Testing approaches used
- Performance optimizations made

### 3. Update Memory (if applicable)
- Store any new patterns or solutions in project memory/documentation
- Update entity relationships discovered
- Add observations about system behavior

### 4. Document Unfinished Work
- What was being worked on when context limit approached
- Exact state of any partially completed features
- Commands that need to be run on restart
- Any temporary workarounds that need permanent fixes

### 5. Handoff Notes in SESSION-NOTES.md
Include in SESSION-NOTES.md if switching to a new conversation:
- Exact file and line being edited (if mid-edit)
- The goal of current changes
- Any uncommitted changes that need attention
- Test commands to verify work
- Critical state information hard to rediscover

## Additional Context: $ARGUMENTS

**Priority**: Focus on capturing information that would be hard to rediscover or reconstruct from code alone.