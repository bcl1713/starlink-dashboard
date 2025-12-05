# Complete Documentation Map

## Project Root

| File                                           | Purpose                                       | Audience     |
| :--------------------------------------------- | :-------------------------------------------- | :----------- |
| [README.md](../../README.md)                   | Project overview, quick start, navigation     | Everyone     |
| [CLAUDE.md](../../CLAUDE.md)                   | AI development guide, configuration reference | Developers   |
| [CONTRIBUTING.md](../../CONTRIBUTING.md)       | How to contribute, development workflow       | Contributors |
| [.env.example](../../.env.example)             | Configuration template with defaults          | Everyone     |
| [docker-compose.yml](../../docker-compose.yml) | Service definition and composition            | DevOps       |

## Documentation (docs/)

### Setup & Installation

| File                                              | Purpose                                   | When to read                |
| :------------------------------------------------ | :---------------------------------------- | :-------------------------- |
| [setup/installation.md](../setup/installation.md) | Complete setup instructions for all modes | Setting up the project      |
| [api/README.md](../api/README.md)                 | All REST API endpoints with examples      | Using the API               |
| [ROUTE-TIMING-GUIDE.md](../ROUTE-TIMING-GUIDE.md) | Route timing feature complete guide       | Using route timing features |

### Mission Communication Planning

| File                                                               | Purpose                                                    | When to read                              |
| :----------------------------------------------------------------- | :--------------------------------------------------------- | :---------------------------------------- |
| [MISSION-PLANNING-GUIDE.md](../missions/MISSION-PLANNING-GUIDE.md) | Mission planning interface and workflow guide              | Using mission planner                     |
| [MISSION-COMM-SOP.md](../missions/MISSION-COMM-SOP.md)             | Operations playbook for mission planning and monitoring    | Planning and executing missions           |
| [PERFORMANCE-NOTES.md](../PERFORMANCE-NOTES.MD)                    | Performance benchmarking results and optimization guidance | Understanding performance characteristics |

### Reference

| File                                                                                | Purpose                                   | When to read          |
| :---------------------------------------------------------------------------------- | :---------------------------------------- | :-------------------- |
| [METRICS](../metrics/overview.md)                                                   | Complete Prometheus metrics documentation | Understanding metrics |
| [troubleshooting/quick-diagnostics.md](../troubleshooting/quick-diagnostics.md)     | Problem diagnosis and solutions           | Troubleshooting       |

### Architecture & Design

| File                                                                   | Purpose                                  | When to read                |
| :--------------------------------------------------------------------- | :--------------------------------------- | :-------------------------- |
| [architecture/design-document.md](../architecture/design-document.md)  | System architecture and design decisions | Understanding architecture  |
| [phased-development-plan.md](../phased-development-plan.md)            | Implementation roadmap and phases        | Understanding plan          |
| [Grafana Configuration](../grafana-configuration.md)                   | Dashboard configuration and usage        | Learning Grafana dashboards |

### Development (development/)

| File                                                                          | Purpose                                  | When to read               |
| :---------------------------------------------------------------------------- | :--------------------------------------- | :------------------------- |
| [development/claude-code/README.md](../development/claude-code/)              | Claude Code workflows guide (main entry) | AI-assisted development    |
| [development/claude-code/agents.md](../development/claude-code/agents.md)     | Complete agent reference                 | Using Claude Code agents   |
| [development/claude-code/commands.md](../development/claude-code/commands.md) | Slash commands reference                 | Using development commands |
| [development/claude-code/skills.md](../development/claude-code/skills.md)     | Skills system reference                  | Using Claude Code skills   |
| [development/claude-code/examples.md](../development/claude-code/examples.md) | Practical workflows                      | Learning by example        |

## Backend (backend/starlink-location/)

| File                                                                                           | Purpose                          | When to read           |
| :--------------------------------------------------------------------------------------------- | :------------------------------- | :--------------------- |
| [README.md](../../backend/starlink-location/README.md)                                         | Backend service overview and API | Developing backend     |
| [VALIDATION.md](../../backend/starlink-location/VALIDATION.md)                                 | Testing and validation guide     | Testing                |
| [VALIDATION-TROUBLESHOOTING.md](../../backend/starlink-location/VALIDATION-TROUBLESHOOTING.md) | Validation troubleshooting       | Debugging tests        |
| [config.yaml](../../backend/starlink-location/config.yaml)                                     | Default configuration            | Understanding defaults |
| [requirements.txt](../../backend/starlink-location/requirements.txt)                           | Python dependencies              | Dependency management  |

## Development (dev/)

| File                               | Purpose                                    | When to read                 |
| :--------------------------------- | :----------------------------------------- | :--------------------------- |
| [STATUS.md](../../dev/STATUS.md)   | Current development status and progress    | Understanding current work   |
| [README.md](../../dev/README.md)   | Development workflow and task management   | Starting development         |
| [completed/](../../dev/completed/) | Archived completed tasks and documentation | Learning from completed work |
