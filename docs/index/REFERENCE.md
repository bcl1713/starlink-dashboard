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
- Detailed Setup: [SETUP-GUIDE.md](../SETUP-GUIDE.md)
- Simulation Mode:
  [SETUP-GUIDE.md#simulation-mode-setup](../SETUP-GUIDE.md#simulation-mode-setup)
- Live Mode: [SETUP-GUIDE.md#live-mode-setup](../SETUP-GUIDE.md#live-mode-setup)
- Verification: [SETUP-GUIDE.md#verification](../SETUP-GUIDE.md#verification)
- Troubleshooting Setup:
  [TROUBLESHOOTING.md#service-wont-start](../TROUBLESHOOTING.md#service-wont-start)

**Configuration:**

- Environment Variables:
  [README.md#configuration](../../README.md#configuration)
- .env Reference: [CLAUDE.md#configuration](../../CLAUDE.md#configuration)
- Backend Config:
  [backend/README.md#environment-variables](../../backend/starlink-location/README.md#environment-variables)
- Docker Compose: [docker-compose.yml](../../docker-compose.yml)

**API & Endpoints:**

- Quick Reference: [API-REFERENCE.md](../API-REFERENCE.md)
- Backend Service:
  [backend/README.md](../../backend/starlink-location/README.md)
- Examples:
  [API-REFERENCE.md#api-usage-examples](../API-REFERENCE.md#api-usage-examples)

**Monitoring & Metrics:**

- Metrics Reference: [METRICS.md](../METRICS.md)
- Prometheus Config:
  [monitoring/prometheus/prometheus.yml](../../monitoring/prometheus/prometheus.yml)
- Grafana Setup: [grafana-setup.md](../grafana-setup.md)
- Dashboard Features:
  [README.md#grafana-dashboards](../../README.md#grafana-dashboards)
- Mission Monitoring:
  [monitoring/README.md#mission-communication-planning](../../monitoring/README.md#mission-communication-planning)

**Mission Communication Planning:**

- User Guide: [MISSION-PLANNING-GUIDE.md](../MISSION-PLANNING-GUIDE.md)
- Operations Playbook: [MISSION-COMM-SOP.md](../MISSION-COMM-SOP.md)
- Performance Analysis: [PERFORMANCE-NOTES.md](../PERFORMANCE-NOTES.md)
- Monitoring Setup:
  [monitoring/README.md#mission-communication-planning](../../monitoring/README.md#mission-communication-planning)

**Development & Contributing:**

- How to Contribute: [CONTRIBUTING.md](../../CONTRIBUTING.md)
- Architecture: [design-document.md](../design-document.md)
- Development Status: [dev/STATUS.md](../../dev/STATUS.md)
- Development Plan: [phased-development-plan.md](../phased-development-plan.md)
- Development Config: [CLAUDE.md](../../CLAUDE.md)

**Troubleshooting:**

- Common Issues: [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
- Port Conflicts:
  [TROUBLESHOOTING.md#port-conflicts](../TROUBLESHOOTING.md#port-conflicts)
- Backend Issues:
  [TROUBLESHOOTING.md#backend-issues](../TROUBLESHOOTING.md#backend-issues)
- Network Issues:
  [TROUBLESHOOTING.md#network--connectivity](../TROUBLESHOOTING.md#network--connectivity)
- Live Mode Issues:
  [TROUBLESHOOTING.md#live-mode-issues](../TROUBLESHOOTING.md#live-mode-issues)

### By Audience

**First-Time Users:**

- Start here: [README.md](../../README.md)
- Then read: [SETUP-GUIDE.md](../SETUP-GUIDE.md)

**Operators/DevOps:**

- Setup: [SETUP-GUIDE.md](../SETUP-GUIDE.md)
- Troubleshooting: [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
- Configuration: [CLAUDE.md](../../CLAUDE.md)

**Developers:**

- Architecture: [design-document.md](../design-document.md)
- Contributing: [CONTRIBUTING.md](../../CONTRIBUTING.md)
- API Reference: [API-REFERENCE.md](../API-REFERENCE.md)

**API Consumers:**

- Quick Start: [API-REFERENCE.md#quick-start](../API-REFERENCE.md)
- Examples:
  [API-REFERENCE.md#api-usage-examples](../API-REFERENCE.md#api-usage-examples)
- Interactive Docs: <http://localhost:8000/docs>

---

## File Size Reference

| File                       | Size  | Type      | Purpose                         |
| -------------------------- | ----- | --------- | ------------------------------- |
| README.md                  | 14 KB | Overview  | Project entry point             |
| SETUP-GUIDE.md             | 18 KB | How-to    | Detailed setup instructions     |
| API-REFERENCE.md           | 22 KB | Reference | Complete API documentation      |
| TROUBLESHOOTING.md         | 24 KB | Reference | Problem diagnosis and solutions |
| design-document.md         | 9 KB  | Design    | Architecture and design         |
| CONTRIBUTING.md            | 18 KB | Process   | Contribution guidelines         |
| grafana-setup.md           | 12 KB | How-to    | Dashboard configuration         |
| METRICS.md                 | 8 KB  | Reference | Prometheus metrics              |
| phased-development-plan.md | 7 KB  | Plan      | Implementation roadmap          |
| CLAUDE.md                  | 8 KB  | Config    | Development configuration       |
| Backend README             | 14 KB | Overview  | Service documentation           |

**Total Documentation:** ~154 KB of comprehensive guides

---

## Quick Links

### Most Useful Pages

- [README.md](../../README.md) - Start here
- [SETUP-GUIDE.md](../SETUP-GUIDE.md) - How to set up
- [API-REFERENCE.md](../API-REFERENCE.md) - API endpoints
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Fix problems
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
- See [dev/STATUS.md](../../dev/STATUS.md) for current work
- Reference specific file and line number
