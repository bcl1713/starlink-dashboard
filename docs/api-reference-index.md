# API reference index

The v1.0.0 backend provides telemetry, route and POI management, Mission V2
planning, native Overview settings and aviation weather APIs.

Start with the [API guide](api/README.md),
[endpoint catalog](api/endpoints/README.md), [models](api/models/README.md),
[examples](api/examples/README.md) and [error handling](api/errors.md).

Mission lifecycle uses `/api/v2/missions`; `/api/missions` is retired. See
[activation and restart behavior](api/endpoints/README.md#mission-v2-activation).
Route upload and standalone route management remain under `/api/routes`;
[route management](route-api-endpoints.md) describes that separate contract.

The Mission Planner at `http://localhost:5173` uses same-origin `/api/...`
requests. Direct backend clients use `http://localhost:8000` by default. Use
`/pois` in the frontend for POI management; backend `/ui/pois` remains a legacy
HTML interface.

The running backend provides [Swagger UI](http://localhost:8000/docs),
[ReDoc](http://localhost:8000/redoc) and its
[OpenAPI schema](http://localhost:8000/openapi.json). These expose exact request
and response schemas for the deployed build, including newer optional fields.

No application authentication is configured by default; configure access at the
deployment boundary. Rate limits are endpoint-specific: KML upload is limited to
10 requests per minute. Clients should handle HTTP 429 as well as validation and
lifecycle conflicts.
