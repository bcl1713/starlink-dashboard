# Practical Workflows

This document provides complete workflows for common development tasks in this
project.

---

## Workflow 1: Adding a New Prometheus Metric

**Scenario:** You want to add a new metric for satellite signal quality.

**Steps:**

1. **Plan the implementation:**

   ```text
   /dev-docs Add satellite signal quality metric to Prometheus
   ```

   This creates a detailed plan in `dev/active/signal-quality-metric/`

2. **Implement the metric:**

   Edit `backend/starlink-location/app/api/metrics.py` and add your metric code.

3. **Review the implementation:**

   ```text
   "Review the new signal quality metric I just added"
   ```

   The `code-architecture-reviewer` agent examines your code.

4. **Document the metric:**

   ```text
   "Update docs/METRICS.md to include the new signal quality metric"
   ```

   Or use the `documentation-architect` agent for comprehensive docs.

5. **Update task tracking:**

   ```text
   /dev-docs-update Completed signal quality metric implementation
   ```

---

## Workflow 2: Creating a New Grafana Dashboard

**Scenario:** You want to create a new dashboard for satellite health monitoring.

**Steps:**

1. **Research best practices:**

   ```text
   "Research best practices for Grafana satellite monitoring dashboards"
   ```

   The `web-research-specialist` agent finds examples and patterns.

2. **Plan the dashboard:**

   ```text
   /dev-docs Create satellite health monitoring dashboard
   ```

3. **Create the dashboard JSON:**

   Edit a file in `monitoring/grafana/provisioning/dashboards/`

   The `grafana-dashboard` skill auto-activates and provides guidance.

4. **Test the dashboard:**

   Load it in Grafana at <http://localhost:3000>

5. **Document the dashboard:**

   ```text
   "Add documentation for the satellite health dashboard to docs/grafana-setup.md"
   ```

---

## Workflow 3: Refactoring Existing Code

**Scenario:** The metrics collection code is getting messy and needs refactoring.

**Steps:**

1. **Create a refactoring plan:**

   ```text
   "Create a refactoring plan for backend/starlink-location/app/api/metrics.py"
   ```

   The `refactor-planner` agent analyzes the code and creates a detailed plan.

2. **Review the plan:**

   ```text
   "Review this refactoring plan before I start implementation"
   ```

   The `plan-reviewer` agent validates the approach.

3. **Execute the refactoring:**

   Follow the plan step-by-step, making changes incrementally.

4. **Review each significant change:**

   ```text
   "Review the metrics collector refactoring I just completed"
   ```

5. **Update documentation:**

   ```text
   /dev-docs-update Completed metrics collector refactoring
   ```

---

## Workflow 4: Debugging a Complex Issue

**Scenario:** Prometheus scrapes are timing out intermittently.

**Steps:**

1. **Research the problem:**

   ```text
   "Research common causes of Prometheus scrape timeouts with FastAPI"
   ```

   The `web-research-specialist` agent searches for solutions.

2. **Create a debugging plan:**

   ```text
   /dev-docs Debug and fix Prometheus scrape timeout issues
   ```

3. **Document findings as you debug:**

   Keep notes in `dev/active/scrape-timeout-debug/[task]-context.md`

4. **Review the fix:**

   ```text
   "Review my fix for the Prometheus timeout issue"
   ```

5. **Document the solution:**

   ```text
   "Add this to troubleshooting docs so we don't hit this again"
   ```

6. **Update task tracking:**

   ```text
   /dev-docs-update Fixed Prometheus timeout by optimizing metrics calculation
   ```

---

## Workflow 5: Adding a Major New Feature

**Scenario:** You want to add real-time alerting when satellite signal drops
below a threshold.

**Steps:**

1. **Create comprehensive plan:**

   ```text
   /dev-docs Implement real-time alerting system for satellite signal quality
   ```

2. **Review the plan before starting:**

   ```text
   "Review the alerting system plan"
   ```

   The `plan-reviewer` agent validates the approach.

3. **Research implementation patterns:**

   ```text
   "Research best practices for implementing alerting with Prometheus and Grafana"
   ```

4. **Implement in phases:**

   Follow the tasks in `dev/active/alerting-system/alerting-system-tasks.md`

   After each phase:

   ```text
   "Review the alert rule configuration I just added"
   ```

5. **Document the system:**

   ```text
   "Create comprehensive documentation for the alerting system"
   ```

   The `documentation-architect` agent creates detailed docs.

6. **Update progress regularly:**

   ```text
   /dev-docs-update Completed phase 1 of alerting system (alert rules)
   ```

---

## Tips for This Project

### Prometheus Metrics

When adding new metrics, always:

1. Use `web-research-specialist` to verify naming conventions
2. Document in `docs/METRICS.md`
3. Test scraping with `curl http://localhost:8000/metrics`
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
2. Check health endpoint: `curl http://localhost:8000/health`
3. Review FastAPI docs for async patterns
4. Use type hints consistently

### Development Task Management

Use the `dev/active/` directory for all major work:

- Persists across context resets
- Provides clear handoff documentation
- Tracks progress with checklists
- Captures important decisions
