# Forge internal-network compatibility probe — #391 / #408

Authorized by [checkpoint 6363968731](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6363968731). Single operational experiment, no application launch or correction.

Observed 2026-10-23 11:38:51.504100–11:38:55.287022 UTC, **3.782975 seconds including teardown**, runner exit 0; no command timed out. Each case had a 15-second deadline; outer invocation was `timeout --signal=TERM --kill-after=10s 60s python3 evidence/network-probe-20261023/probe.py`. Tool session 73422 completed. The script and command ledger preserve exact commands, times, statuses, PID/PGID ownership and sanitized Docker/Compose selectors.

Daemon `forge`, ID `deea92b2-886d-484b-aeb7-2ccdb87aa94a`, Docker 29.8.1, overlayfs, rootless security option; Compose v5.5.1. Context reports `default`; explicit inherited `DOCKER_HOST=unix:///run/user/1002/docker.sock` selects the actor daemon and was preserved. Managed environment-status tool and `/etc/codex/network-policy.json` were unavailable. Host commands used approved execution; no daemon settings changed.

Cached non-application `nginx:alpine` (103 MB listing), pinned to local image ID `sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d`; entrypoint `nginx`, arguments `-g 'daemon off;'`. No build or pull. Project `p391-net-20261023-1149`, one container per case, sequential fresh networks. Ports 43891/43892 verified free by host bind and listener inspection. Both configurations are identical except `networks.default.internal` and the required distinct host ports. Rendered Case 2 omits the false default; its effective network explicitly reports `Internal=false`.

| Evidence | Case 1: internal true | Case 2: internal false |
|---|---|---|
| Rendered binding | 127.0.0.1:43891 → 80/tcp | 127.0.0.1:43892 → 80/tcp |
| HostConfig.PortBindings | 80/tcp: HostIp 127.0.0.1, HostPort 43891 | 80/tcp: HostIp 127.0.0.1, HostPort 43892 |
| Config.ExposedPorts | `{"80/tcp":{}}` | `{"80/tcp":{}}` |
| NetworkSettings.Ports | `{"80/tcp":null}` | `{"80/tcp":[{"HostIp":"127.0.0.1","HostPort":"43892"}]}` |
| Network driver / Internal / Options | bridge / true / `{}` | bridge / false / `{}` |
| Compose ps | running, PublishedPort 0 | running, PublishedPort 43892 |
| docker port | empty, exit 0 | `80/tcp -> 127.0.0.1:43892`, exit 0 |
| Host ss listener | absent | rootlesskit PID 2575950, 127.0.0.1:43892 |
| Single HTTP check | connection refused, curl exit 7 | HTTP 200, curl exit 0 |

Both `compose up` commands exited 0; both containers were running, State.Error empty, and Nginx worker startup logs present. Case 2 logs include its single successful GET. Each HTTP command used `--retry 0 --connect-timeout 1 --max-time 2 --noproxy '*'`. All other recorded commands exited 0. Logs and stdout/stderr are retained separately; `commands.jsonl` binds each artifact to its exact argv/status/timestamps.

**Finding:** internal-network selection changes actual host-port publication in this Forge environment. Compose rendering requests both bindings and Docker persists both in HostConfig; Docker runtime network realization exposes no published mapping for the internal bridge. The non-internal bridge realizes the mapping, rootlesskit listens, and host HTTP succeeds. This disproves a general inability of rootless forwarding to publish ports here. HostConfig is evidence of persisted binding requests; the raw create API payload was not captured. This probe does not identify the precise Docker/libnetwork implementation branch or establish behavior on other versions/environments. It corroborates the prior A symptom without retroactively recovering A's missing HostConfig evidence or qualifying A/C.

**Smallest proposed correction, not applied:** in the task-owned diagnostic Compose override, set the affected default network to `internal: false` (equivalently remove the diagnostic `internal: true` where no inherited true remains):

```yaml
networks:
  default:
    internal: false
```

This would permit ordinary bridge egress, so it changes diagnostic isolation as well as port realization. It requires checkpoint review. No production configuration, diagnostic launcher, A/C configuration or accepted images were changed. No A/C smoke, calibration, sustained test, new test suite or application traffic occurred. Frozen 1.5-second observer requirement and 78/90/10 A deadlines remain unchanged.

**Cleanup:** each case used scoped `compose down --volumes --remove-orphans --timeout 1`; final scoped down exited 0. Temporary input Compose files were removed; exact rendered configs and reproducible input-generation script remain as evidence. Independent approved host audit at 11:39:29 UTC found no project containers, networks or volumes, no listeners on either port, successful bind checks for both ports, and no surviving recorded runner/command/container/worker/shim PIDs. Shared rootlesskit is preserved. No task-owned runtime resources remain.

The first audit assertion compared raw image-list order and failed because Docker reordered the listing. This audit failure is retained in `host-post-audit.json`; `audit-interpretation.json` records the corrected comparison of complete tag/ID sets: identical, no added/removed/changed images. In particular all four accepted A/C diagnostic image tags and IDs remain unchanged. Existing evidence was only read.

GitHub status readback: #403/#405/#406/#407/#408 remain open draft/unmerged; #404 is an open issue, not a PR. #390/#391 remain open. Primary checkout remains on dev. Evidence lives on a separate branch from origin/dev; delivery is a comment on existing draft #408, with no PR state or head change. **STOP for checkpoint review; A/C remain NO-GO.**
