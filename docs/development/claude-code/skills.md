# Skills System Reference

Context-aware guidelines that automatically activate based on what you're
working on.

[Back to main guide →](./README.md)

---

## Currently Installed Skills

### `skill-developer`

**Purpose:** Meta-skill for creating and managing Claude Code skills.

**Auto-activates when:**

- Editing `.claude/skills/` files
- Discussing skill triggers, rules, or hooks
- Keywords: "skill system", "create skill", "skill triggers"

**Use when:** Building custom skills for your project.

---

### `grafana-dashboard`

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

## How Skills Work

### Automatic Activation

The `skill-activation-prompt` hook monitors your prompts and file edits. When it
detects relevant keywords or file patterns, it suggests the appropriate skill.

### Manual Activation

You can explicitly request a skill:

```text
"Use the grafana-dashboard skill to help me create a new panel"
```

### Skill Suggestion

When a skill is suggested but not automatically loaded, you can accept or
decline:

- Accept: "Yes, use that skill"
- Decline: Continue without it

---

## File Locations

Skills are installed in the `.claude/` directory:

```text
.claude/
├── skills/
│   ├── grafana-dashboard/
│   │   ├── rules.json
│   │   └── guidance.md
│   ├── skill-developer/
│   │   ├── rules.json
│   │   └── guidance.md
│   └── skill-rules.json
└── hooks/
    └── skill-activation-prompt.sh
```

---

## Creating Custom Skills

To create a custom skill for your project:

1. Create a new directory in `.claude/skills/[skill-name]/`
2. Add `rules.json` with trigger conditions
3. Add `guidance.md` with skill instructions
4. The `skill-developer` skill can help you build these

**Ask:** "Create a new skill for [task]" and the skill-developer agent will
guide you through the process.

---

## Tips for Using Skills

### Let Skills Activate Automatically

When editing relevant files, skills often activate automatically. You'll see a
suggestion popup.

### Be Specific in Your Requests

Instead of:

```text
"Help with Grafana"
```

Try:

```text
"I'm creating a new dashboard panel that shows real-time satellite
position data"
```

### Combine with Agents

Skills provide contextual guidance, while agents do deeper analysis:

- **Skill:** "You should use geomap panel here"
- **Agent:** "Let me review your entire dashboard design"

### Disable if Needed

If a skill is interfering with your workflow, you can temporarily decline it or
disable it in `skill-rules.json`.

---

## Common Skill Use Cases

### Working on Grafana Dashboards

When editing `monitoring/grafana/provisioning/dashboards/`:

1. Skill activates automatically
2. Follow its guidance for PromQL queries
3. Use panel templates from existing dashboards
4. Skill suggests best practices for your metric type

### Working on Skills Themselves

When editing `.claude/skills/`:

1. The `skill-developer` skill activates
2. It provides guidance on rule syntax
3. It helps with trigger patterns
4. It suggests guidance content structure

---

## Advanced: Understanding Skill Rules

Skills use a rules-based system to determine when to activate:

```json
{
  "name": "grafana-dashboard",
  "triggers": {
    "file_patterns": ["monitoring/grafana/**/*.json"],
    "keywords": ["grafana", "dashboard", "promql"]
  },
  "priority": 5,
  "auto_activate": true
}
```

**file_patterns:** Glob patterns that trigger the skill

**keywords:** Words or phrases that trigger the skill

**priority:** How important this skill is (higher = more prominent)

**auto_activate:** Whether to activate automatically or wait for confirmation

For more details, see `.claude/skills/skill-rules.json` in your project.
