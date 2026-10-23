"""Bounded, owner-executed HTTP gate. Container running alone is never ready."""

import asyncio
import json
import sys
import time

from prepare import write

# Runs as an owned child: socket stalls, slow bodies and DNS cannot outlive command cap.
PROBE = """
import hashlib,http.client,json,sys
c=http.client.HTTPConnection('127.0.0.1',int(sys.argv[1]),timeout=0.5)
try:
 c.request('GET','/',headers={'Accept-Encoding':'identity','Connection':'close'})
 r=c.getresponse(); body=r.read(262145)
 if len(body)>262144: raise ValueError('frontend body budget')
 print(json.dumps({'status':r.status,'sha256':hashlib.sha256(body).hexdigest()}))
finally: c.close()
"""


FORWARDERS = """
import json,os
from pathlib import Path
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit(): continue
 try:
  if p.stat().st_uid != os.getuid(): continue
  name=(p/'comm').read_text().strip()
  if name not in ('rootlesskit','slirp4netns','docker-proxy','pasta','vpnkit'): continue
  rows.append({'pid':int(p.name),'comm':name,'argv':(p/'cmdline').read_bytes()[:4096].replace(b'\\0',b' ').decode(errors='replace')})
 except (OSError,ValueError): continue
 if len(rows)>=32: break
print(json.dumps(rows))
"""


def bounded_argv(argv, cap):
    # Leave 50 ms TERM grace and 50 ms for exit observation/owner bookkeeping.
    # This prevents a TERM-resistant probe consuming Owner.close's fallback windows.
    if cap <= 0.1:
        raise TimeoutError("insufficient command/termination budget")
    return ["timeout", "--kill-after=0.05s", str(cap - 0.1) + "s", *argv]


async def wait_ready(command, dc, root, port, expected_hash, deadline, stop):
    until = min(deadline, time.monotonic() + 5)
    record = {"status": "waiting", "attempts": [], "deadline_monotonic": until}
    try:
        while True:
            if stop.is_set():
                record["status"] = "cancelled"
                raise RuntimeError("frontend readiness signal")
            if time.monotonic() >= until:
                record["status"] = "deadline"
                raise TimeoutError("frontend HTTP readiness deadline")
            attempt = {"utc_ns": time.time_ns(), "monotonic": time.monotonic()}
            record["attempts"].append(attempt)
            write(root / "frontend-readiness.json", record)
            try:

                async def run(argv):
                    return await command(
                        argv, min(0.75, max(0.001, until - time.monotonic()))
                    )

                cid = (await run([*dc, "ps", "-aq", "mission-planner"])).strip()
                if not cid or len(cid.splitlines()) != 1:
                    raise RuntimeError("frontend container identity unavailable")
                state = json.loads(
                    await run(["docker", "inspect", cid, "--format", "{{json .State}}"])
                )
                attempt["state"] = state
                if (
                    state.get("Status") in ("exited", "dead", "removing")
                    or state.get("Health", {}).get("Status") == "unhealthy"
                ):
                    record["status"] = "container-failed"
                    raise RuntimeError("frontend exited or unhealthy")
                if not state.get("Running"):
                    raise RuntimeError("frontend not running")
                response = json.loads(
                    await run([sys.executable, "-B", "-c", PROBE, str(port)])
                )
                attempt["response"] = response
                if (
                    response.get("status") != 200
                    or response.get("sha256") != expected_hash
                ):
                    raise ValueError("unexpected frontend HTTP status/content")
                if time.monotonic() >= until or stop.is_set():
                    raise TimeoutError("frontend success after deadline/signal")
                record["status"] = "ready"
                return
            except Exception as error:
                attempt["error"] = type(error).__name__ + ": " + str(error)[:512]
                if record["status"] == "container-failed":
                    raise
                # command timeouts leave an owned child potentially alive: reap via finally,
                # never start another command until that owner has closed.
                if isinstance(error, TimeoutError):
                    record["status"] = "timeout"
                    raise
            finally:
                attempt["finished_monotonic"] = time.monotonic()
                write(root / "frontend-readiness.json", record)
            await asyncio.sleep(min(0.2, max(0, until - time.monotonic())))
    except BaseException:
        if record["status"] == "waiting":
            record["status"] = "failed"
        raise
    finally:
        write(root / "frontend-readiness.json", record)


async def snapshot(command, dc, root, port, deadline):
    """Best effort, 1.5 seconds total, at most .25 seconds per observation."""
    until = min(deadline, time.monotonic() + 1.5)
    rows = []
    cid = None
    queries = [
        ("compose-ps", [*dc, "ps", "-a", "--format", "json"]),
        ("container-id", [*dc, "ps", "-aq", "mission-planner"]),
        ("inspect", None),
        ("port", None),
        (
            "frontend-logs",
            [*dc, "logs", "--no-color", "--tail", "80", "mission-planner"],
        ),
        ("listeners", ["ss", "-ltnp", "sport = :" + str(port)]),
        (
            "forwarding",
            [sys.executable, "-B", "-c", FORWARDERS],
        ),
    ]
    for name, argv in queries:
        row = {"kind": name, "utc_ns": time.time_ns(), "monotonic": time.monotonic()}
        rows.append(row)
        if name == "inspect":
            argv = (
                [
                    "docker",
                    "inspect",
                    cid,
                    "--format",
                    '{"State":{{json .State}},"Ports":{{json .NetworkSettings.Ports}}}',
                ]
                if cid
                else None
            )
        elif name == "port":
            argv = ["docker", "port", cid] if cid else None
        try:
            if not argv or time.monotonic() >= until:
                raise RuntimeError("identity unavailable or diagnostic deadline")
            row["output"] = (await command(argv, min(0.25, until - time.monotonic())))[
                :32768
            ]
            if name == "container-id":
                value = row["output"].strip()
                cid = value if value and len(value.splitlines()) == 1 else None
        except BaseException as error:
            row["error"] = type(error).__name__ + ": " + str(error)[:512]
        write(root / "frontend-failure-diagnostics.json", rows)
