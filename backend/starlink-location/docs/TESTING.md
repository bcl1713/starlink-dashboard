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
4. Update documentation if adding features or changing test warning provenance

---

## Warning provenance

The backend test suite intentionally leaves one third-party-only deprecation warning
visible rather than suppressing it. With FastAPI 0.141.1, Starlette 1.6.0, and
AnyIO 4.15.1, Starlette 1.6.0's `testclient.py:53` uses the deprecated
`anyio.abc.BlockingPortal` alias. This source is vendor code, so it is documented
instead of being globally suppressed.

`httpx2>=2.0.0` is required because Starlette 1.6.0 expects it for `TestClient`;
it removes the separate FastAPI/Starlette TestClient deprecation warning without
changing application test behavior.

---

[Back to Backend README](../README.md)
