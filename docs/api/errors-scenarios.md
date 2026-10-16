# Common API error scenarios

See [error formats](errors.md). Examples below describe status and response
shape; validation wording can vary with dependency versions.

| Request or condition                                 | Expected behavior                                            | Action                                        |
| ---------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| POST `/api/pois/` with latitude 100                  | 422, `detail` contains validation errors                     | Use latitude -90..90 and longitude -180..180  |
| GET `/api/pois/missing-id`                           | 404, `{"detail":"POI not found: missing-id"}`                | List POIs and select an existing ID           |
| DELETE `/api/pois/{id}` succeeds                     | 204, empty body                                              | Do not call `response.json()`                 |
| Missing required ETA location query arguments        | 422 request validation                                       | Supply the arguments in the endpoint schema   |
| Invalid configuration request schema                 | 422 request validation                                       | Inspect `detail` and the configuration schema |
| Configuration update fails after validation          | 400, string `detail`                                         | Inspect backend logs and configuration        |
| GET `/api/routes/active/timing` with no active route | 200, `{"has_timing_data":false,"message":"No active route"}` | Select a route or activate a mission leg      |
| Delete an active Mission V2 leg                      | 409 lifecycle conflict                                       | Deactivate before deleting                    |
| GET `/health` before coordinator initialization      | 503, `{"detail":"Service not yet initialized"}`              | Check startup logs                            |

Do not depend on a negative `speed_knots` query producing a uniform validation
error: the POI ETA endpoint accepts string query values and its conversion and
fallback behavior differs from Pydantic-validated POI coordinates. See the
[POI ETA limitations](poi/eta-endpoints.md#calculation-method).

```bash
curl -i 'http://localhost:8000/api/pois/missing-id'
curl 'http://localhost:8000/api/pois/?active_only=false' | jq '.pois[] | {id, name}'
```
