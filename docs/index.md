# Starlink Dashboard Documentation Index

**Last Updated:** 2025-12-05 **Status:** Complete - 7-category structure with
audience-based navigation **Purpose:** Master index for all Starlink Dashboard
documentation

---

## Documentation by Category

The documentation is organized into 7 main categories based on purpose and
audience:

### 1. [Setup](setup/README.md)

**Purpose:** Installation, configuration, and initial deployment **Audience:**
Users, operators, first-time installers

Covers system prerequisites, installation procedures, configuration options, and
quick start guides.

### 2. [Troubleshooting](troubleshooting/README.md)

**Purpose:** Problem diagnosis and resolution **Audience:** Users, operators,
support staff

Organized by service and symptom for quick access to solutions for common
issues.

### 3. [API Reference](api/README.md)

**Purpose:** REST API endpoints, models, and integration examples **Audience:**
API consumers, integrators, developers

Complete technical reference for endpoints, request/response models,
authentication, and code examples.

### 4. [Features](features/README.md)

**Purpose:** System capabilities and user-facing functionality **Audience:**
Users, evaluators, product stakeholders

Describes what the system does, feature use cases, and system behavior.

### 5. [Architecture](architecture/README.md)

**Purpose:** System design, technical decisions, and internal structure
**Audience:** Developers, contributors, technical evaluators

Explains how the system works internally, design rationale, and technical
implementation details.

### 6. [Development](development/README.md)

**Purpose:** Contributing, testing, and development workflows **Audience:**
Contributors, developers

Guides for development environment setup, testing procedures, code quality
standards, and contribution guidelines.

### 7. [Reports](reports/README.md)

**Purpose:** Historical documentation and completed work artifacts **Audience:**
Project historians, retrospective reviewers

Archive of implementation summaries, feature analysis reports, and project
retrospectives.

---

## Documentation by Audience

### For Users & Operators

Start here to install, configure, and operate the Starlink Dashboard:

1. **Getting Started**: [Setup Guide](setup/quick-start.md)
2. **Configuration**: [Setup Documentation](setup/README.md)
3. **Using Features**: [Features Overview](features/README.md)
4. **Fixing Problems**: [Troubleshooting Guide](troubleshooting/README.md)

### For Developers & Contributors

Start here to understand the system and contribute code:

1. **Onboarding**: [Quick Start](setup/quick-start.md) →
   [Architecture Overview](architecture/design-document.md)
2. **Contributing**: [Development Workflow](development/workflow.md) →
   [CONTRIBUTING.md](../CONTRIBUTING.md)
3. **System Design**: [Architecture Documentation](architecture/README.md)
4. **Testing**: [Testing Guide](development/README.md)

### For API Consumers & Integrators

Start here to integrate with the Starlink Dashboard API:

1. **Getting Started**: [API Overview](api/README.md)
2. **Endpoints**: [API Endpoints](api/endpoints/README.md)
3. **Data Models**: [API Models](api/models/README.md)
4. **Code Examples**: [API Examples](api/examples/README.md)

---

## Additional Resources

### Legacy Index Structure

The previous index system is still available for reference:

- [Navigation Guide](index/guide.md) - Use case-based documentation access
- [Complete Documentation Map](index/map.md) - Detailed file listing by location
- [Documentation by Format](index/formats.md) - Organized by documentation type
- [Documentation Reference](index/reference.md) - Searchable topics and quick
  links

### Root-Level Documentation

Essential project documentation at the repository root:

- [README.md](../README.md) - Project overview and quick links
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines and standards
- [CLAUDE.md](../CLAUDE.md) - Runtime guidance for AI-assisted development
- [AGENTS.md](../AGENTS.md) - Agent configuration

### Backend-Specific Documentation

Service implementation details:

- [Backend Architecture](../backend/starlink-location/docs/ARCHITECTURE.md)
- [Backend Testing Guide](../backend/starlink-location/docs/TESTING.md)
- [Troubleshooting](../backend/starlink-location/docs/TROUBLESHOOTING.md)

### Specification Documents

Feature planning and design specifications:

---

## Finding What You Need

### Quick Search

Use these patterns to find documentation:

| I need to...                    | Look in...                                    |
| ------------------------------- | --------------------------------------------- |
| Install or configure the system | [setup/](setup/README.md)                     |
| Fix a problem or error          | [troubleshooting/](troubleshooting/README.md) |
| Understand an API endpoint      | [api/](api/README.md)                         |
| Learn about a feature           | [features/](features/README.md)               |
| Understand system architecture  | [architecture/](architecture/README.md)       |
| Contribute or run tests         | [development/](development/README.md)         |
| Find historical reports         | [reports/](reports/README.md)                 |

### Documentation Standards

All documentation follows these principles:

- **Organized by purpose**: Each category serves a specific documentation need
- **Audience-focused**: Clear separation between user and developer
  documentation
- **Navigable**: Every category has a README.md index with descriptions
- **Maintainable**: Files kept under 300 lines, clear naming conventions
- **Linked**: Relative paths for portability, comprehensive cross-references

---

**Need Help?**

- **Documentation questions**: See [CONTRIBUTING.md](../CONTRIBUTING.md) for
  structure guidelines
- **Technical questions**: See
  [Architecture Documentation](architecture/README.md)
- **Support**: See [Troubleshooting](troubleshooting/README.md)
