# Contributing to Starlink Dashboard

**Last Updated:** 2025-11-04
**Status:** Foundation + Major Features Complete - Ready for Contributors
**Current Phase:** ETA Route Timing Complete (all 451 tests passing)

Thank you for your interest in contributing to the Starlink Dashboard project! This guide provides everything you need to get started.

## Quick Navigation

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)
- [Project Structure](#project-structure)

---

## Code of Conduct

Be respectful, inclusive, and professional. This project welcomes contributions from developers of all skill levels.

---

## Getting Started

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Git
- Python 3.9+ (for local development)

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-repo/starlink-dashboard.git
   cd starlink-dashboard
   git checkout dev
   ```

2. **Create your feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set up development environment:**
   ```bash
   cp .env.example .env
   docker compose build
   docker compose up -d
   ```

4. **Verify setup:**
   ```bash
   curl http://localhost:8000/health
   open http://localhost:3000
   ```

---

## Development Workflow

### 1. Understand the Project

**Read core documentation:**
- [README.md](./README.md) - Project overview
- [CLAUDE.md](./CLAUDE.md) - Development configuration
- [docs/design-document.md](./docs/design-document.md) - Architecture overview
- [docs/phased-development-plan.md](./docs/phased-development-plan.md) - Implementation phases

### 2. Find Issues to Work On

**Look for:**
- Issues labeled `good first issue`
- Issues in the current development phase
- Feature requests in [GitHub Issues](./issues)

**Check development status:**
- [dev/STATUS.md](./dev/STATUS.md) - Current phase and active work
- [dev/README.md](./dev/README.md) - Task structure and workflow

### 3. Plan Your Work

**Before coding:**
1. Create a task folder in `/dev/active/[task-name]/`
2. Run `/dev-docs` slash command to generate planning documents
3. Document your approach in task files
4. Get feedback on the plan before implementation

### 4. Implement the Feature

**During development:**
1. Work on your feature branch
2. Update code according to plan
3. Write tests for new functionality
4. Update documentation as you go
5. Keep task checklist updated

**Best practices:**
- Make atomic commits (one logical change per commit)
- Write clear commit messages
- Test frequently with `docker compose up -d && docker compose logs -f`
- Reference related files with line numbers in documentation

### 5. Test Your Changes

**Local testing:**
```bash
# Build and test
docker compose build
docker compose up -d

# Run tests (when available)
docker compose exec starlink-location pytest tests/

# Manual testing
curl http://localhost:8000/api/status
# Open http://localhost:3000 in browser
```

**Validation checklist:**
- All containers start without errors
- Health endpoints return 200
- Data flows from backend to Prometheus to Grafana
- New features work as intended
- No regressions in existing features

### 6. Commit and Push

**Commit your work:**
```bash
git add .
git commit -m "type: brief description"
```

**Push to your fork:**
```bash
git push origin feature/your-feature-name
```

---

## Commit Guidelines

### Format

```
type: brief description (50 chars max)

Longer explanation if needed. Explain the "why" not just the "what".

References: #123 (related issue number)
```

### Types

Use conventional commit types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation update
- `refactor:` - Code refactoring (no functional change)
- `test:` - Test additions/changes
- `chore:` - Build, dependencies, etc.

### Examples

**Good commits:**
```
feat: add ETA calculations for POIs

Implements Haversine formula to calculate great-circle distance
and estimated time of arrival to each point of interest. ETA
updates in real-time based on current position and speed.

Fixes: #45
```

```
fix: resolve POI file locking issue

Added filelock library to prevent concurrent access errors when
multiple processes write to POI file simultaneously.

Related: #78
```

**Bad commits:**
```
update code
Fixed stuff
WIP
```

---

## Pull Request Process

### Before Creating PR

1. **Update from dev branch:**
   ```bash
   git fetch origin
   git rebase origin/dev
   ```

2. **Run final tests:**
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   # Test manually
   docker compose logs -f
   ```

3. **Update documentation:**
   - Update README if needed
   - Update API docs for new endpoints
   - Add troubleshooting if introducing new complexity

### Creating the PR

**Use GitHub:**
1. Push your branch to GitHub
2. Click "Create Pull Request"
3. Fill in PR template (see below)

**PR Title:** Same format as commit messages
```
feat: add ETA calculations for POIs
```

**PR Description Template:**

```markdown
## Description
Brief explanation of what this PR does.

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Documentation update
- [ ] Refactoring

## Changes Made
- What specifically was changed
- Any new files or directories
- Any dependencies added

## Testing
How was this tested? What should reviewers test?

## Screenshots (if applicable)
Include Grafana screenshots for UI changes.

## Related Issues
Fixes #123
Related to #456

## Checklist
- [ ] Code follows project style
- [ ] Tests pass (if applicable)
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Commit messages follow guidelines
```

### Review Process

1. **Code review:** Maintainer reviews your code
2. **Feedback:** Address any requested changes
3. **Approval:** PR approved and ready to merge
4. **Merge:** Code merged to dev branch
5. **Integration:** Test in dev environment

---

## Testing

### Running Tests

```bash
# Unit tests
docker compose exec starlink-location pytest tests/unit/ -v

# Integration tests
docker compose exec starlink-location pytest tests/integration/ -v

# All tests with coverage
docker compose exec starlink-location pytest tests/ --cov=app --cov-report=html
```

### Writing Tests

**For new features, add tests to:**
- `backend/starlink-location/tests/unit/` - Unit tests
- `backend/starlink-location/tests/integration/` - Integration tests

**Test file structure:**
```python
import pytest
from app.your_module import your_function

def test_your_function():
    """Test description."""
    result = your_function(test_input)
    assert result == expected_output

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await your_async_function()
    assert result is not None
```

### Test Coverage Goals

- **Unit tests:** > 80% code coverage
- **Integration tests:** All endpoints tested
- **Manual testing:** Verify in Grafana UI

---

## Documentation

### When to Update Documentation

Update docs for:
- New features or endpoints
- Configuration changes
- Troubleshooting discovered issues
- Architecture changes

### Files to Update

| Change | Files to Update |
|--------|-----------------|
| New API endpoint | `docs/API-REFERENCE.md` |
| New configuration | `docs/SETUP-GUIDE.md`, `CLAUDE.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md` |
| New metrics | `docs/METRICS.md` |
| Architecture | `docs/design-document.md` |
| Grafana changes | `docs/grafana-setup.md` |

### Documentation Standards

- Use clear, technical language
- Include code examples for complex concepts
- Update table of contents
- Cross-reference related sections
- Keep relative links working
- Use absolute paths in file references

---

## Project Structure

### Directory Layout

```
starlink-dashboard/
├── backend/                           # Python backend service
│   └── starlink-location/
│       ├── app/
│       │   ├── api/                   # API endpoints
│       │   ├── core/                  # Core functionality
│       │   ├── models/                # Pydantic models
│       │   ├── services/              # Business logic
│       │   ├── simulation/            # Simulation engine
│       │   └── live/                  # Live mode client
│       ├── tests/                     # Test suite
│       ├── main.py                    # FastAPI app
│       ├── config.yaml                # Default config
│       └── requirements.txt           # Python dependencies
├── monitoring/                        # Monitoring stack
│   ├── prometheus/
│   │   └── prometheus.yml             # Prometheus config
│   └── grafana/
│       └── provisioning/              # Grafana configs
├── docs/                              # Documentation
│   ├── design-document.md             # Architecture
│   ├── phased-development-plan.md     # Implementation plan
│   ├── API-REFERENCE.md               # API endpoints
│   ├── SETUP-GUIDE.md                 # Setup instructions
│   ├── TROUBLESHOOTING.md             # Troubleshooting
│   └── METRICS.md                     # Prometheus metrics
├── dev/                               # Development planning
│   ├── active/                        # Active tasks
│   ├── completed/                     # Archived tasks
│   ├── STATUS.md                      # Current status
│   └── README.md                      # Workflow docs
├── docker-compose.yml                 # Service composition
├── .env.example                       # Example configuration
├── CLAUDE.md                          # AI assistant guidance
├── README.md                          # Project overview
└── CONTRIBUTING.md                    # This file
```

### Key Files for Developers

**Must read:**
- `CLAUDE.md` - Development configuration
- `docker-compose.yml` - Service setup
- `backend/starlink-location/main.py` - Backend entry point
- `docs/design-document.md` - Architecture

**Reference often:**
- `docs/API-REFERENCE.md` - Endpoints
- `docs/TROUBLESHOOTING.md` - Common issues
- `backend/starlink-location/requirements.txt` - Dependencies

---

## Development Best Practices

### Code Style

```python
# Follow PEP 8
# Use 4-space indentation
# Use type hints where possible

def calculate_eta(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    speed_knots: float
) -> float:
    """Calculate ETA in seconds using Haversine formula.

    Args:
        lat1: Starting latitude
        lon1: Starting longitude
        lat2: Destination latitude
        lon2: Destination longitude
        speed_knots: Speed in knots

    Returns:
        ETA in seconds
    """
    pass
```

### Git Workflow

```bash
# Stay updated
git fetch origin
git rebase origin/dev

# Clean up
git branch -d feature/old-feature
git push origin --delete feature/old-feature

# Before creating PR
git log origin/dev..HEAD  # See your commits
```

### Docker Best Practices

```bash
# Always rebuild after config changes
docker compose down
docker compose build --no-cache
docker compose up -d

# Check logs for errors
docker compose logs -f

# Clean up when done
docker compose down
docker system prune
```

---

## Common Development Tasks

### Adding a New API Endpoint

1. **Create endpoint in `backend/starlink-location/app/api/`**
   ```python
   from fastapi import APIRouter, HTTPException

   router = APIRouter(prefix="/api/new", tags=["new"])

   @router.get("/status")
   async def get_status():
       """Get new feature status."""
       return {"status": "ok"}
   ```

2. **Register in `main.py`**
   ```python
   from app.api import new_feature
   app.include_router(new_feature.router)
   ```

3. **Add tests in `tests/`**

4. **Update `docs/API-REFERENCE.md`**

5. **Commit and create PR**

### Adding a New Metric

1. **Define in `app/core/metrics.py`**
   ```python
   new_metric = Gauge(
       'starlink_new_metric',
       'Description of new metric'
   )
   ```

2. **Update in simulation/live coordinator**

3. **Add to tests**

4. **Update `docs/METRICS.md`**

### Creating a New Feature

1. **Create task folder:** `mkdir -p dev/active/feature-name`

2. **Run planning:** `/dev-docs "feature description"`

3. **Implement following checklist**

4. **Create feature branch:** `git checkout -b feature/feature-name`

5. **Commit regularly**

6. **Create PR when ready**

---

## Release Process

When ready for release:

1. **Create release branch:**
   ```bash
   git checkout -b release/v0.3.0
   ```

2. **Update version:**
   - `backend/starlink-location/main.py`
   - Docker image tags

3. **Update CHANGELOG**

4. **Create PR and merge to main**

5. **Tag release:**
   ```bash
   git tag -a v0.3.0 -m "Release version 0.3.0"
   git push origin v0.3.0
   ```

---

## Getting Help

### Resources

- [README.md](./README.md) - Project overview
- [CLAUDE.md](./CLAUDE.md) - Configuration guide
- [Design Document](./docs/design-document.md) - Architecture
- [API Reference](./docs/API-REFERENCE.md) - Endpoints
- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues

### Communication

- **Issues:** Use GitHub Issues for bugs and features
- **Discussions:** Use GitHub Discussions for questions
- **Code Review:** Expect feedback on PRs

---

## Current Development Status

**Phase 0:** Foundation ✅ Complete
**Phase 1+:** Feature development - See [dev/STATUS.md](./dev/STATUS.md)

**Most Needed Contributions:**
- Automated testing framework
- Additional Grafana dashboard improvements
- Documentation enhancements
- Performance optimizations

---

Thank you for contributing to Starlink Dashboard!
