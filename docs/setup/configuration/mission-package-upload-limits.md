# Mission Package Upload Limit

[Back to Configuration](README.md) | [Mission package import behavior](../../missions/mission-package-import.md) | [Back to Setup](../README.md)

---

## Contract

Mission Planner accepts one mission-package ZIP request up to **100 MiB**
(104,857,600 bytes) at `POST /api/v2/missions/import`.

The limit applies to the uploaded ZIP request body, before extraction. It is not
a limit on the uncompressed contents of the ZIP or on an individual file inside
it. A package whose uploaded ZIP is larger than 100 MiB is rejected and is not
imported.

## Required Aligned Enforcement

Every proxy or application layer that can receive the import must use the same
100 MiB limit. A lower limit causes that layer to reject a package before a
later layer can evaluate it.

| Enforcement point                                         | Required setting                                       | Managed source                                               |
| --------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| Mission Planner frontend Nginx                            | `client_max_body_size 100m;`                           | `frontend/mission-planner/nginx.conf`                        |
| Nginx Proxy Manager (NPM), when it fronts Mission Planner | `client_max_body_size 100m;` and the 413 handler       | `deployment/nginx-proxy-manager/mission-package-upload.conf` |
| Backend application                                       | `MISSION_PACKAGE_MAX_UPLOAD_BYTES = 100 * 1024 * 1024` | `backend/starlink-location/app/mission/routes_v2.py`         |

Do not raise only one layer. Keep all three values aligned whenever the contract
changes.

## Deploy or Update

### Docker Compose Mission Planner

The tracked Mission Planner Nginx configuration is baked into the frontend
image. From the repository root, rebuild and restart after pulling the version
that contains the configuration:

```bash
docker compose down
docker compose build --no-cache mission-planner
docker compose up -d
docker compose ps
```

If the backend image is also being updated, use the repository's full rebuild
procedure instead:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose ps
curl http://localhost:8000/health
```

### Nginx Proxy Manager

NPM is outside the repository's Docker Compose deployment. When NPM fronts the
Mission Planner, copy or mount
`deployment/nginx-proxy-manager/mission-package-upload.conf` into the Mission
Planner Proxy Host's **server context**, then apply the NPM configuration
change. The snippet must remain in the server context because it defines both
the body-size limit and the named 413 error handler.

The repository does not change a host-managed NPM instance automatically. An
operator must apply and verify this snippet for each NPM deployment. Other
reverse-proxy products and topologies are not configured by this repository;
operators using them must implement an equivalent 100 MiB limit and structured
413 response before treating large uploads as supported.

## Verify the Deployed Contract

1. Confirm the stack is healthy:

   ```bash
   docker compose ps
   curl http://localhost:8000/health
   ```

2. In Mission Planner, export or prepare a valid mission package representative
   of production use. Use a package larger than the former default proxy limit;
   the implementation smoke check used a valid 21 MiB ZIP and imported three
   legs with no warnings.

3. Import that package through the same public URL used by operators (including
   NPM when present). Confirm the import succeeds and the expected legs appear.

4. Exercise the rejection path with a ZIP larger than 100 MiB. The
   implementation smoke check used a 101 MiB ZIP. Confirm it returns HTTP 413,
   not HTTP 500, and does not create a partial mission.

A command-line check can use the same API endpoint when a valid test package is
available:

```bash
curl --fail-with-body --show-error --location \
  --form "file=@mission-package.zip;type=application/zip" \
  http://localhost:5173/api/v2/missions/import
```

Use the externally reachable NPM URL instead of `http://localhost:5173` when
verifying the NPM path.

## Over-Limit Error and Diagnosis

Mission Planner displays an over-limit response as:

> Mission package exceeds the 100 MiB limit (rejected by `<layer>`).

The response is HTTP 413 with a JSON `detail` object. It always includes:

- `code`: `mission_package_too_large`
- `layer`: the component that rejected the upload
- `max_bytes`: `104857600`

The backend application response also includes `received_bytes` because it has
read the uploaded file. A proxy can reject the request before that field is
available.

| `layer` value           | Meaning and next action                                                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `nginx-proxy-manager`   | NPM rejected the request. Verify the Proxy Host server-context snippet and reload/apply the NPM configuration.                                   |
| `mission-planner-nginx` | The Mission Planner container rejected the request. Verify the deployed frontend image was rebuilt from the tracked Nginx configuration.         |
| `application`           | The backend received the upload and enforced the limit. Verify its deployed version and keep proxy limits aligned with the application constant. |

If the response is HTML, lacks `layer`, or is not HTTP 413, the request probably
went through an unconfigured intermediary. Inspect that proxy's request-body
limit and error handling before retrying.

---

[Back to Configuration](README.md) | [Mission package import behavior](../../missions/mission-package-import.md) | [Back to Setup](../README.md)
