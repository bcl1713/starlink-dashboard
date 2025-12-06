# Practical Workflows & Examples

Real-world workflows for common development tasks in this project.

[Back to main guide →](./README.md)

---

## Workflow 1: Adding a New Prometheus Metric

1. Plan: `/dev-docs Add satellite signal quality metric to Prometheus`
2. Implement in `backend/starlink-location/app/api/metrics.py`
3. Review: `"Review the new signal quality metric I just added"`
4. Document: Update `docs/METRICS.md`
5. Track: `/dev-docs-update Completed signal quality metric`

---

## Workflow 2: Creating a New Grafana Dashboard

1. Research: `"Research best practices for Grafana dashboards"`
2. Plan: `/dev-docs Create satellite health monitoring dashboard`
3. Create in `monitoring/grafana/provisioning/dashboards/`
4. Test at `http://localhost:3000`
5. Document: Update `docs/grafana-setup.md`

---

## Workflow 3: Refactoring Existing Code

1. Plan: `"Create a refactoring plan for [code]"`
2. Review: `"Review this plan before I start"`
3. Execute: Make changes incrementally
4. Review changes: `"Review the refactoring"`
5. Track: `/dev-docs-update Completed refactoring`

---

## Workflow 4: Debugging Complex Issues

1. Research: `"Research common causes of [problem]"`
2. Plan: `/dev-docs Debug and fix [issue]`
3. Fix: Implement and test the solution
4. Review: `"Review my fix for [issue]"`
5. Document: Add to `docs/troubleshooting.md`
6. Track: `/dev-docs-update Fixed [issue]`

---

## Workflow 5: Adding Major Features

1. Plan: `/dev-docs Implement [feature]`
2. Review: `"Review the [feature] plan"`
3. Research: `"Research best practices for [feature]"`
4. Implement: Follow phased approach in task checklist
5. Document: `"Create documentation for [feature]"`
6. Track: `/dev-docs-update Completed phase 1 of [feature]`

---

## Best Practices by Task Type

### For New Features

1. **Start with `/dev-docs`** - Creates persistent structure
2. **Use `plan-reviewer`** to validate before coding
3. **Update with `/dev-docs-update`** regularly
4. **Review with `code-architecture-reviewer`** after implementation

### For Bug Fixes

1. **Use `web-research-specialist`** to find similar issues
2. **Create minimal reproduction** with step-by-step plan
3. **Review the fix** with `code-architecture-reviewer`
4. **Add to troubleshooting docs** with `documentation-architect`

### For Refactoring

1. **Plan with `refactor-planner`** before making changes
2. **Make incremental changes** - don't refactor everything at once
3. **Review each phase** with `code-architecture-reviewer`
4. **Test thoroughly** after refactoring

### For Documentation

1. **Create docs as you go** - Don't wait until the end
2. **Use `documentation-architect`** for comprehensive docs
3. **Update existing docs** when adding features
4. **Document "why" decisions** in context files

---

## Common Patterns

### Quick Problem Solving

```text
"Research [the problem]"
→ Gets solutions from community
```

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

### After Implementing

```text
"Review [what I just built]"
→ Gets architectural feedback
```

### Need Comprehensive Docs

```text
"Document [system/feature]"
→ Creates detailed documentation
```

---

## Project-Specific Tips

### Working with Metrics & Dashboards

**Prometheus Metrics:**

1. Verify naming with `web-research-specialist`
2. Document in `docs/METRICS.md`
3. Test: `curl http://localhost:8000/metrics`
4. Review with `code-architecture-reviewer`

**Grafana Dashboards:**

1. Let `grafana-dashboard` skill guide you
2. Test queries in Grafana's builder first
3. Commit to `monitoring/grafana/provisioning/dashboards/`
4. Document in `docs/grafana-setup.md`

### Backend & Task Management

**Backend Code:** Use simulation mode for testing, check health endpoint with
`curl http://localhost:8000/health`, use type hints consistently.

**Task Management:** Use `dev/active/` directory - it persists across context
resets and provides clear handoff documentation.
