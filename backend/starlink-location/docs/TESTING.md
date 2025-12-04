# Testing Guide

[Back to Backend README](../README.md)

---

## Unit Tests

```bash
pytest tests/unit/ -v
```

Tests included for:

- Configuration loading and validation
- Route generation (circular and straight)
- Position simulator
- Network simulator
- Obstruction simulator
- Prometheus metrics

---

## Integration Tests

```bash
pytest tests/integration/ -v
```

Tests included for:

- Health endpoint
- Metrics endpoint
- Status endpoint
- Configuration API
- End-to-end simulation

---

## Run All Tests with Coverage

```bash
pytest tests/ --cov=app --cov-report=html
```

---

## Contributing

When making changes:

1. Update tests in `tests/`
2. Ensure all tests pass: `pytest tests/`
3. Run with coverage: `pytest tests/ --cov=app`
4. Update documentation if adding features

---

[Back to Backend README](../README.md)
