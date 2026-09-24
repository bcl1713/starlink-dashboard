# Testing Guide

[Back to Backend README](../README.md)

## Canonical Backend Gate

Run the complete backend suite with the repository-root command:

```bash
./tools/verify backend
```

Use the focused `pytest` examples below while working in
`backend/starlink-location`. For all verification tiers, see the
[Quality Gates](../../../docs/contributing/quality-gates.md) reference.

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
2. Run `./tools/verify backend` from the repository root before merge
3. Use `pytest tests/` and `pytest tests/ --cov=app` as focused local examples
4. Update documentation if adding features or changing test warning provenance

---

## Warning provenance

The backend test suite leaves residual third-party warnings visible rather than
suppressing them. A fresh dependency inventory identifies the following
vendor-owned sources:

- Starlette 1.6.0 / AnyIO 4.15.1: `testclient.py:53` uses the deprecated
  `anyio.abc.BlockingPortal` alias.
- Cartopy 0.26.0: `feature_artist.py:142` warns that `facecolor` has no effect.
- SlowAPI 0.1.10: `extension.py:737` uses the legacy 413 status constant.
- reverse-geocoder 1.5: `rg_cities1000.csv` is left open, producing a
  `ResourceWarning`.

These warnings are vendor-owned and remain visible. Do not suppress them or
upgrade dependencies solely to hide them.

---

[Back to Backend README](../README.md)
