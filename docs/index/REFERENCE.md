# Documentation Reference & Search

## Documentation Statistics

| Category                       | Count  | Total Pages    |
| ------------------------------ | ------ | -------------- |
| Setup & Getting Started        | 2      | ~40 pages      |
| API & Integration              | 3      | ~60 pages      |
| Mission Communication Planning | 3      | ~180 pages     |
| Troubleshooting & Reference    | 2      | ~40 pages      |
| Feature Guides                 | 2      | ~100 pages     |
| Architecture & Design          | 4      | ~50 pages      |
| Development & Contributing     | 4      | ~30 pages      |
| Backend Service                | 2      | ~20 pages      |
| Monitoring & Operations        | 1      | ~50 pages      |
| **Total**                      | **23** | **~570 pages** |

---

## Search & Find

### By Topic

**Installation & Setup:**

- Quick Start: [README.md#quick-start](../../README.md#quick-start)
- Detailed Setup: [setup/installation.md](../setup/installation.md)
- Simulation Mode:
  [setup/configuration/simulation-mode.md](../setup/configuration/simulation-mode.md)
- Live Mode:
  [setup/configuration/live-mode.md](../setup/configuration/live-mode.md)
- Verification: [setup/installation.md#verification](../setup/installation.md#verification)
- Troubleshooting Setup:
  [troubleshooting/quick-diagnostics.md#service-issues](../troubleshooting/quick-diagnostics.md#service-issues)

**Configuration:**

- Environment Variables:
  [README.md#configuration](../../README.md#configuration)
- .env Reference: [CLAUDE.md#configuration](../../CLAUDE.md#configuration)
- Backend Config:
  [backend/README.md#environment-variables](../../backend/starlink-location/README.md#environment-variables)
- Docker Compose: [docker-compose.yml](../../docker-compose.yml)

**API & Endpoints:**

- Quick Reference: [api/README.md](../api/README.md)
- Backend Service:
  [backend/README.md](../../backend/starlink-location/README.md)
- Examples: [api/examples/README.md](../api/examples/README.md)

**Monitoring & Metrics:**

- Metrics Reference: [METRICS](../metrics/overview.md)
- Prometheus Config:
  [monitoring/prometheus/prometheus.yml](../../monitoring/prometheus/prometheus.yml)
- Grafana Setup: [Grafana Configuration](../grafana-configuration.md)
- Dashboard Features:
  [README.md#grafana-dashboards](../../README.md#grafana-dashboards)
- Mission Monitoring:
  [monitoring/README.md#mission-communication-planning](../../monitoring/README.md#mission-communication-planning)

**Mission Communication Planning:**

- User Guide:
  [MISSION-PLANNING-GUIDE.md](../missions/MISSION-PLANNING-GUIDE.md)
- Operations Playbook: [MISSION-COMM-SOP.md](../missions/MISSION-COMM-SOP.md)
- Performance Analysis: [PERFORMANCE-NOTES.md](../PERFORMANCE-NOTES.md)
- Monitoring Setup:
  [monitoring/README.md#mission-communication-planning](../../monitoring/README.md#mission-communication-planning)

**Development & Contributing:**

- How to Contribute: [CONTRIBUTING.md](../../CONTRIBUTING.md)
- Architecture:
  [architecture/design-document.md](../architecture/design-document.md)
- Development Status: [Development Plan](../development-plan.md)
- Development Plan: [Development Plan](../development-plan.md)
- Development Config: [CLAUDE.md](../../CLAUDE.md)

**Troubleshooting:**

- Common Issues:
  [troubleshooting/quick-diagnostics.md](../troubleshooting/quick-diagnostics.md)
- Port Conflicts:
  [troubleshooting/quick-diagnostics.md#port-conflicts](../troubleshooting/quick-diagnostics.md#port-conflicts)
- Backend Issues:
  [troubleshooting/data-issues.md](../troubleshooting/data-issues.md)
- Network Issues:
  [troubleshooting/quick-diagnostics.md#network-connectivity](../troubleshooting/quick-diagnostics.md#network-connectivity)
- Live Mode Issues:
  [troubleshooting/quick-diagnostics.md#live-mode-issues](../troubleshooting/quick-diagnostics.md#live-mode-issues)

### By Audience

**First-Time Users:**

- Start here: [README.md](../../README.md)
- Then read: [setup/installation.md](../setup/installation.md)

**Operators/DevOps:**

- Setup: [setup/installation.md](../setup/installation.md)
- Troubleshooting:
  [troubleshooting/quick-diagnostics.md](../troubleshooting/quick-diagnostics.md)
- Configuration: [CLAUDE.md](../../CLAUDE.md)

**Developers:**

- Architecture:
  [architecture/design-document.md](../architecture/design-document.md)
- Contributing: [CONTRIBUTING.md](../../CONTRIBUTING.md)
- API Reference: [api/README.md](../api/README.md)

**API Consumers:**

- Quick Start: [api/README.md](../api/README.md)
- Examples: [api/examples/README.md](../api/examples/README.md)
- Interactive Docs: <http://localhost:8000/docs>

---

## File Size Reference

| File                                     | Size  | Type      | Purpose                         |
| ---------------------------------------- | ----- | --------- | ------------------------------- |
| README.md                                | 14 KB | Overview  | Project entry point             |
| setup/installation.md                    | 18 KB | How-to    | Detailed setup instructions     |
| api/README.md                            | 22 KB | Reference | Complete API documentation      |
| troubleshooting/quick-diagnostics.md     | 24 KB | Reference | Problem diagnosis and solutions |
| architecture/design-document.md          | 9 KB  | Design    | Architecture and design         |
| CONTRIBUTING.md                          | 18 KB | Process   | Contribution guidelines         |
| grafana-configuration.md                 | 12 KB | How-to    | Dashboard configuration         |
| metrics/overview.md                      | 8 KB  | Reference | Prometheus metrics              |
| phased-development-plan.md               | 7 KB  | Plan      | Implementation roadmap          |
| CLAUDE.md                                | 8 KB  | Config    | Development configuration       |
| Backend README                           | 14 KB | Overview  | Service documentation           |

**Total Documentation:** ~154 KB of comprehensive guides

---

## Quick Links

### Most Useful Pages

- [README.md](../../README.md) - Start here
- [setup/installation.md](../setup/installation.md) - How to set up
- [api/README.md](../api/README.md) - API endpoints
- [troubleshooting/quick-diagnostics.md](../troubleshooting/quick-diagnostics.md)
  \- Fix problems
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - How to contribute

### External Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

### Interactive Documentation

- Backend API Docs: <http://localhost:8000/docs>
- Prometheus UI: <http://localhost:9090>
- Grafana Dashboards: <http://localhost:3000>

---

## How This Documentation is Organized

The documentation follows these principles:

1. **Layered Detail:** Start simple, add complexity as needed
2. **Task-Based:** Organized around what users want to do
3. **Cross-Referenced:** Links between related topics
4. **Searchable:** Clear structure for quick lookup
5. **Discoverable:** Multiple ways to find what you need

Each document has:

- Clear title and purpose
- Table of contents
- Navigation links
- Code examples
- Related documentation references

---

## Maintaining Documentation

Documentation is updated when:

- New features are added
- Architecture changes
- Setup procedures change
- Common issues arise
- User feedback indicates gaps

All documentation uses:

- Clear, technical language
- Markdown formatting
- Consistent structure
- Relative file links
- Code examples

---

## Feedback & Contributions

Found an issue in the documentation?

- Check [CONTRIBUTING.md](../../CONTRIBUTING.md) for how to contribute
- See [Development Plan](../development-plan.md) for current work
- Reference specific file and line number
