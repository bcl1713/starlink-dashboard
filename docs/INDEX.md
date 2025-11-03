# Starlink Dashboard Documentation Index

**Last Updated:** 2025-10-31
**Complete Documentation Map**

## Navigation Guide

This page provides a complete map of all documentation in the Starlink Dashboard project. Use this to quickly find what you're looking for.

---

## Quick Start (5 minutes)

Start here if you're new to the project:

1. **[README.md](../README.md)** - Project overview and quick start
2. **[SETUP-GUIDE.md](./SETUP-GUIDE.md)** - Detailed installation instructions
3. Access: http://localhost:3000 (Grafana)

---

## Documentation by Use Case

### I want to...

#### Set up the project

| Goal | Document | Time |
|------|----------|------|
| Get it running in 3 minutes | [Quick Start (README)](../README.md#quick-start) | 3 min |
| Understand all setup options | [SETUP-GUIDE.md](./SETUP-GUIDE.md) | 10 min |
| Configure simulation mode | [SETUP-GUIDE.md - Simulation](./SETUP-GUIDE.md#simulation-mode-setup) | 5 min |
| Connect to real hardware | [SETUP-GUIDE.md - Live Mode](./SETUP-GUIDE.md#live-mode-setup) | 10 min |
| Fix setup problems | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | varies |

#### Use the dashboards

| Goal | Document | Time |
|------|----------|------|
| Understand available dashboards | [README.md - Dashboards](../README.md#grafana-dashboards) | 5 min |
| Learn dashboard features | [grafana-setup.md](./grafana-setup.md) | 15 min |
| Create custom dashboards | [grafana-setup.md](./grafana-setup.md) | 20 min |
| Understand the metrics | [METRICS.md](./METRICS.md) | 10 min |

#### Develop features

| Goal | Document | Time |
|------|----------|------|
| Understand architecture | [design-document.md](./design-document.md) | 15 min |
| See implementation plan | [phased-development-plan.md](./phased-development-plan.md) | 10 min |
| Contribute code | [CONTRIBUTING.md](../CONTRIBUTING.md) | 15 min |
| Current development status | [dev/STATUS.md](../dev/STATUS.md) | 5 min |
| Review API endpoints | [API-REFERENCE.md](./API-REFERENCE.md) | 15 min |

#### Debug issues

| Goal | Document | Time |
|------|----------|------|
| Service won't start | [TROUBLESHOOTING.md - Service Won't Start](./TROUBLESHOOTING.md#service-wont-start) | 10 min |
| Can't access Grafana | [TROUBLESHOOTING.md - Service Issues](./TROUBLESHOOTING.md#service-wont-start) | 5 min |
| No data appearing | [TROUBLESHOOTING.md - Backend Issues](./TROUBLESHOOTING.md#backend-issues) | 15 min |
| Live mode won't connect | [TROUBLESHOOTING.md - Live Mode](./TROUBLESHOOTING.md#live-mode-issues) | 10 min |
| Port conflicts | [TROUBLESHOOTING.md - Port Conflicts](./TROUBLESHOOTING.md#port-conflicts) | 5 min |

---

## Complete Documentation Map

### Project Root

| File | Purpose | Audience |
|------|---------|----------|
| [README.md](../README.md) | Project overview, quick start, navigation | Everyone |
| [CLAUDE.md](../CLAUDE.md) | AI development guide, configuration reference | Developers |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to contribute, development workflow | Contributors |
| [.env.example](../.env.example) | Configuration template with defaults | Everyone |
| [docker-compose.yml](../docker-compose.yml) | Service definition and composition | DevOps |

### Documentation (docs/)

#### Setup & Installation

| File | Purpose | When to read |
|------|---------|--------------|
| [SETUP-GUIDE.md](./SETUP-GUIDE.md) | Complete setup instructions for all modes | Setting up the project |
| [API-REFERENCE.md](./API-REFERENCE.md) | All REST API endpoints with examples | Using the API |

#### Reference

| File | Purpose | When to read |
|------|---------|--------------|
| [METRICS.md](./METRICS.md) | Complete Prometheus metrics documentation | Understanding metrics |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Problem diagnosis and solutions | Troubleshooting |

#### Architecture & Design

| File | Purpose | When to read |
|------|---------|--------------|
| [design-document.md](./design-document.md) | System architecture and design decisions | Understanding architecture |
| [phased-development-plan.md](./phased-development-plan.md) | Implementation roadmap and phases | Understanding plan |
| [grafana-setup.md](./grafana-setup.md) | Dashboard configuration and usage | Learning Grafana dashboards |
| [claude-code-workflows.md](./claude-code-workflows.md) | Claude-specific development workflows | AI-assisted development |

### Backend (backend/starlink-location/)

| File | Purpose | When to read |
|------|---------|--------------|
| [README.md](../backend/starlink-location/README.md) | Backend service overview and API | Developing backend |
| [VALIDATION.md](../backend/starlink-location/VALIDATION.md) | Testing and validation guide | Testing |
| [config.yaml](../backend/starlink-location/config.yaml) | Default configuration | Understanding defaults |
| [requirements.txt](../backend/starlink-location/requirements.txt) | Python dependencies | Dependency management |

### Development (dev/)

| File | Purpose | When to read |
|------|---------|--------------|
| [STATUS.md](../dev/STATUS.md) | Current development status and progress | Understanding current work |
| [README.md](../dev/README.md) | Development workflow and task management | Starting development |
| [completed/](../dev/completed/) | Archived completed tasks and documentation | Learning from completed work |

---

## Documentation by Format

### Quick Reference (5-10 minutes)

- [README.md Quick Start](../README.md#quick-start)
- [SETUP-GUIDE - Quick Start](./SETUP-GUIDE.md#installation)
- [Troubleshooting - Quick Diagnostics](./TROUBLESHOOTING.md#quick-diagnostics)
- [API Reference - Examples](./API-REFERENCE.md#api-usage-examples)

### How-To Guides (10-20 minutes)

- [SETUP-GUIDE.md](./SETUP-GUIDE.md) - Setup in simulation or live mode
- [CONTRIBUTING.md](../CONTRIBUTING.md) - How to contribute
- [grafana-setup.md](./grafana-setup.md) - Using Grafana dashboards
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Debugging common issues

### Reference Documentation (20+ minutes)

- [design-document.md](./design-document.md) - Full architecture
- [API-REFERENCE.md](./API-REFERENCE.md) - Complete API specification
- [METRICS.md](./METRICS.md) - All metrics reference
- [phased-development-plan.md](./phased-development-plan.md) - Implementation plan
- [Backend README](../backend/starlink-location/README.md) - Service details

### Planning & Status

- [dev/STATUS.md](../dev/STATUS.md) - Current development status
- [phased-development-plan.md](./phased-development-plan.md) - What's planned
- [CONTRIBUTING.md](../CONTRIBUTING.md) - How to get involved

---

## Common Document Combinations

### For First-Time Users

Read in order:
1. [README.md](../README.md) - Overview (5 min)
2. [SETUP-GUIDE.md](./SETUP-GUIDE.md) - Setup (15 min)
3. [grafana-setup.md](./grafana-setup.md) - Using dashboards (10 min)

### For Contributors

Read in order:
1. [README.md](../README.md) - Overview (5 min)
2. [CLAUDE.md](../CLAUDE.md) - Development config (10 min)
3. [design-document.md](./design-document.md) - Architecture (15 min)
4. [CONTRIBUTING.md](../CONTRIBUTING.md) - How to contribute (15 min)
5. [dev/STATUS.md](../dev/STATUS.md) - Current work (5 min)

### For API Users

Read in order:
1. [API-REFERENCE.md](./API-REFERENCE.md) - API endpoints (20 min)
2. [Backend README](../backend/starlink-location/README.md) - Service details (10 min)
3. http://localhost:8000/docs - Interactive docs (5 min)

### For Troubleshooting

1. [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Quick diagnostics (5 min)
2. [SETUP-GUIDE.md](./SETUP-GUIDE.md) - Verify configuration (10 min)
3. [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Specific issue (varies)

### For Operations/DevOps

Read in order:
1. [SETUP-GUIDE.md](./SETUP-GUIDE.md) - Installation (10 min)
2. [SETUP-GUIDE.md - Performance](./SETUP-GUIDE.md#performance-tuning) - Tuning (10 min)
3. [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Monitoring (15 min)

---

## Documentation Statistics

| Category | Count | Total Pages |
|----------|-------|------------|
| Setup & Getting Started | 2 | ~40 pages |
| API & Integration | 2 | ~30 pages |
| Troubleshooting & Reference | 2 | ~40 pages |
| Architecture & Design | 4 | ~50 pages |
| Development & Contributing | 4 | ~30 pages |
| Backend Service | 2 | ~20 pages |
| **Total** | **16** | **~210 pages** |

---

## Search & Find

### By Topic

**Installation & Setup:**
- Quick Start: [README.md#quick-start](../README.md#quick-start)
- Detailed Setup: [SETUP-GUIDE.md](./SETUP-GUIDE.md)
- Simulation Mode: [SETUP-GUIDE.md#simulation-mode-setup](./SETUP-GUIDE.md#simulation-mode-setup)
- Live Mode: [SETUP-GUIDE.md#live-mode-setup](./SETUP-GUIDE.md#live-mode-setup)
- Verification: [SETUP-GUIDE.md#verification](./SETUP-GUIDE.md#verification)
- Troubleshooting Setup: [TROUBLESHOOTING.md#service-wont-start](./TROUBLESHOOTING.md#service-wont-start)

**Configuration:**
- Environment Variables: [README.md#configuration](../README.md#configuration)
- .env Reference: [CLAUDE.md#configuration](../CLAUDE.md#configuration)
- Backend Config: [backend/README.md#environment-variables](../backend/starlink-location/README.md#environment-variables)
- Docker Compose: [docker-compose.yml](../docker-compose.yml)

**API & Endpoints:**
- Quick Reference: [API-REFERENCE.md](./API-REFERENCE.md)
- Backend Service: [backend/README.md](../backend/starlink-location/README.md)
- Examples: [API-REFERENCE.md#api-usage-examples](./API-REFERENCE.md#api-usage-examples)

**Monitoring & Metrics:**
- Metrics Reference: [METRICS.md](./METRICS.md)
- Prometheus Config: [monitoring/prometheus/prometheus.yml](../monitoring/prometheus/prometheus.yml)
- Grafana Setup: [grafana-setup.md](./grafana-setup.md)
- Dashboard Features: [README.md#grafana-dashboards](../README.md#grafana-dashboards)

**Development & Contributing:**
- How to Contribute: [CONTRIBUTING.md](../CONTRIBUTING.md)
- Architecture: [design-document.md](./design-document.md)
- Development Status: [dev/STATUS.md](../dev/STATUS.md)
- Development Plan: [phased-development-plan.md](./phased-development-plan.md)
- Development Config: [CLAUDE.md](../CLAUDE.md)

**Troubleshooting:**
- Common Issues: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Port Conflicts: [TROUBLESHOOTING.md#port-conflicts](./TROUBLESHOOTING.md#port-conflicts)
- Backend Issues: [TROUBLESHOOTING.md#backend-issues](./TROUBLESHOOTING.md#backend-issues)
- Network Issues: [TROUBLESHOOTING.md#network--connectivity](./TROUBLESHOOTING.md#network--connectivity)
- Live Mode Issues: [TROUBLESHOOTING.md#live-mode-issues](./TROUBLESHOOTING.md#live-mode-issues)

### By Audience

**First-Time Users:**
- Start here: [README.md](../README.md)
- Then read: [SETUP-GUIDE.md](./SETUP-GUIDE.md)

**Operators/DevOps:**
- Setup: [SETUP-GUIDE.md](./SETUP-GUIDE.md)
- Troubleshooting: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Configuration: [CLAUDE.md](../CLAUDE.md)

**Developers:**
- Architecture: [design-document.md](./design-document.md)
- Contributing: [CONTRIBUTING.md](../CONTRIBUTING.md)
- API Reference: [API-REFERENCE.md](./API-REFERENCE.md)

**API Consumers:**
- Quick Start: [API-REFERENCE.md#quick-start](./API-REFERENCE.md)
- Examples: [API-REFERENCE.md#api-usage-examples](./API-REFERENCE.md#api-usage-examples)
- Interactive Docs: http://localhost:8000/docs

---

## File Size Reference

| File | Size | Type | Purpose |
|------|------|------|---------|
| README.md | 14 KB | Overview | Project entry point |
| SETUP-GUIDE.md | 18 KB | How-to | Detailed setup instructions |
| API-REFERENCE.md | 22 KB | Reference | Complete API documentation |
| TROUBLESHOOTING.md | 24 KB | Reference | Problem diagnosis and solutions |
| design-document.md | 9 KB | Design | Architecture and design |
| CONTRIBUTING.md | 18 KB | Process | Contribution guidelines |
| grafana-setup.md | 12 KB | How-to | Dashboard configuration |
| METRICS.md | 8 KB | Reference | Prometheus metrics |
| phased-development-plan.md | 7 KB | Plan | Implementation roadmap |
| CLAUDE.md | 8 KB | Config | Development configuration |
| Backend README | 14 KB | Overview | Service documentation |

**Total Documentation:** ~154 KB of comprehensive guides

---

## Quick Links

### Most Useful Pages

- [README.md](../README.md) - Start here
- [SETUP-GUIDE.md](./SETUP-GUIDE.md) - How to set up
- [API-REFERENCE.md](./API-REFERENCE.md) - API endpoints
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Fix problems
- [CONTRIBUTING.md](../CONTRIBUTING.md) - How to contribute

### External Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

### Interactive Documentation

- Backend API Docs: http://localhost:8000/docs
- Prometheus UI: http://localhost:9090
- Grafana Dashboards: http://localhost:3000

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
- Check [CONTRIBUTING.md](../CONTRIBUTING.md) for how to contribute
- See [dev/STATUS.md](../dev/STATUS.md) for current work
- Reference specific file and line number

---

**Last Updated:** 2025-10-31
**Total Documentation:** 16 files, ~210 pages
**Comprehensive Coverage:** Setup, API, Troubleshooting, Architecture, Development
