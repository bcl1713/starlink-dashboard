# ETA cache and accuracy metrics

| Endpoint                               | Result                                               |
| -------------------------------------- | ---------------------------------------------------- |
| GET `/api/routes/metrics/eta-cache`    | Current in-memory cache statistics                   |
| GET `/api/routes/metrics/eta-accuracy` | Current bounded prediction history statistics        |
| POST `/api/routes/cache/cleanup`       | `status`, `entries_removed`, `message`               |
| POST `/api/routes/cache/clear`         | `{"status":"success","message":"ETA cache cleared"}` |

The shared cache uses a five-second TTL; history retains up to 100 records.
These are process-local diagnostics, not durable historical analytics. Accuracy
fields depend on recorded predictions/arrivals; no complete set of recent
prediction rows or nonempty error statistics is guaranteed.

```bash
curl http://localhost:8000/api/routes/metrics/eta-cache | jq .
curl http://localhost:8000/api/routes/metrics/eta-accuracy | jq .
```

Source: `app/api/routes/cache.py`, `app/services/route_eta/cache.py` and
`app/services/eta_cache.py`. See [ETA index](README.md).
