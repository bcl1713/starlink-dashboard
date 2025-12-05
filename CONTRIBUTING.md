# Contributing to Starlink Dashboard

Thank you for contributing to the Starlink Dashboard project! This guide will
help you get started.

---

## Quick Links

- [Development Workflow](./docs/development/workflow.md) - Git practices and
  development process
- [Code Quality Standards](/.specify/memory/constitution.md) - Quality
  principles and guidelines
- [Architecture Documentation](./docs/architecture/README.md) - System design
  and structure

---

## Getting Started

### 1. Set Up Development Environment

Follow the [setup guide](./docs/setup/README.md) to install dependencies and
start services.

### 2. Understand the Codebase

Review the [architecture documentation](./docs/architecture/design-document.md)
to understand system design and component organization.

### 3. Find an Issue or Feature

Check the issue tracker for open issues, or propose a new feature through an
issue discussion.

---

## Development Workflow

### Making Changes

1. **Create a branch** from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following code quality standards

3. **Test your changes**:
   - Backend: Run smoke tests and type checks
   - Frontend: Run linting and build
   - Documentation: Validate links and formatting

4. **Commit with clear messages**:

   ```bash
   git commit -m "feat: add new capability"
   git commit -m "fix: resolve issue with X"
   git commit -m "docs: update API documentation"
   ```

5. **Push and create pull request**:

   ```bash
   git push -u origin feature/your-feature-name
   ```

### Backend Changes (Python)

**CRITICAL**: Backend Python changes require full Docker rebuild:

```bash
docker compose down && docker compose build --no-cache && \
  docker compose up -d && docker compose ps
curl http://localhost:8000/health  # Verify changes took effect
```

See [development workflow](./docs/development/workflow.md) for details.

---

## Documentation Guidelines

### Documentation Structure

All project documentation is organized in `docs/` with seven categories:

- **setup/** - Installation and configuration guides
- **api/** - API reference documentation
- **features/** - Feature descriptions and capabilities
- **troubleshooting/** - Problem-solving guides
- **architecture/** - System design and technical decisions
- **development/** - Developer guides and workflows
- **reports/** - Historical artifacts and completed work

### Adding or Updating Documentation

#### 1. Find the Right Location

Use this decision tree to determine where documentation belongs:

- **Getting started/installation** → `docs/setup/`
- **Fixing problems** → `docs/troubleshooting/`
- **API specifications** → `docs/api/`
- **System architecture** → `docs/architecture/`
- **Development workflows** → `docs/development/`
- **User-facing features** → `docs/features/`
- **Historical reports** → `docs/reports/`

#### 2. Documentation Standards

All documentation files must follow these standards:

- **File naming**: Use `lowercase-with-hyphens.md` format
- **File size**: Keep files ≤300 lines (split if larger)
- **Links**: Always use relative paths (e.g., `../api/README.md`)
- **Headers**: Include clear H1 title at the top
- **Purpose statement**: For docs >100 lines, include brief purpose

Example format:

```markdown
# Document Title

**Purpose**: Brief description of what this document covers
**Audience**: Who should read this

## Section 1

Content...

## Related Documentation

- [Related Doc](../category/file.md)
```

#### 3. Update Category Indexes

When adding new documentation, update the appropriate category's `README.md`
to include your new file in the listing.

#### 4. Validate Links

Before committing, ensure all markdown links work correctly:

```bash
# Manual validation
rg '\[.*\]\((.*\.md[^)]*)\)' your-file.md

# Or use markdown-link-check if installed
markdown-link-check your-file.md
```

### Documentation Quick Reference

For detailed documentation structure and guidelines, see:

- [Documentation Quick Start](./specs/002-docs-cleanup/quickstart.md) -
  Contributor guide to documentation structure
- [Documentation Taxonomy](./specs/002-docs-cleanup/data-model.md) - Complete
  category definitions and rules

---

## Code Quality Standards

### General Principles

- Follow the [Constitution](/.specify/memory/constitution.md) for quality
  principles
- Maintain file size limits (≤300 lines for most files)
- Write clear, self-documenting code
- Include docstrings for all public functions/classes
- Preserve backward compatibility (no breaking changes without discussion)

### Python Backend

- Use type hints for all function signatures
- Follow PEP 8 style guidelines
- Keep functions focused and single-purpose
- Run mypy for type checking

### TypeScript Frontend

- Use TypeScript strict mode
- Minimize use of `any` types
- Follow component-based architecture
- Keep components under 300 lines

### Markdown Documentation

- Use CommonMark specification
- Keep files under 300 lines
- Use relative links only
- Follow naming conventions

---

## Testing

- **Backend**: Run smoke tests after changes
- **Frontend**: Run linting and build process
- **Documentation**: Validate links and formatting

---

## Pull Request Process

1. **Ensure tests pass** and code quality standards are met
2. **Update documentation** if adding/changing features
3. **Write clear PR description** explaining changes and rationale
4. **Reference related issues** using keywords (fixes #123, closes #456)
5. **Wait for review** and address feedback

---

## Questions or Issues?

- Review [troubleshooting guide](./docs/troubleshooting/README.md)
- Check existing issues in the issue tracker
- Ask in pull request comments or create a new issue

---

**Thank you for contributing!**
