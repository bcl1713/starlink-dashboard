# API error handling

Error bodies depend on the handler. There is no API-wide `error_code` or
`timestamp` guarantee. Ordinary FastAPI HTTP errors usually return:

```json
{ "detail": "POI not found: missing-id" }
```

Request validation normally returns HTTP 422 with `detail` as a list of field
errors (`loc`, `msg`, `type` and sometimes additional context). Some feature
handlers use structured detail objects. Unhandled exceptions are handled by
`main.py` with HTTP 500 and `detail` plus `error_type`. Proxies may return
non-JSON bodies. Branch on HTTP status and the documented endpoint contract;
inspect the type of `detail` before displaying it.

| Status    | Typical meaning                                            |
| --------- | ---------------------------------------------------------- |
| 200 / 201 | Successful read/update or creation                         |
| 204       | Successful deletion, no response body                      |
| 400       | Endpoint rejected input or calculation failed              |
| 404       | Resource or endpoint not found                             |
| 409       | Lifecycle conflict, such as deleting an active mission leg |
| 422       | Request schema/type/range validation failed                |
| 429       | Endpoint rate limit exceeded                               |
| 500       | Internal failure or unavailable endpoint dependency        |
| 503       | Service initialization or feature availability failure     |

The POI CRUD implementation does not promise unique names or a duplicate-name
409 response. Resource identity comes from its generated ID.

See [common scenarios](errors-scenarios.md) and
[client handling](errors-handling.md). The running `/openapi.json` and endpoint
implementation define feature-specific errors.
