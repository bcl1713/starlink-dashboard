"""Exact-SHA background PDF acceptance, timings, browser journey, and teardown."""

import argparse
import json
import os
import signal
import subprocess
import tarfile
import time
from pathlib import Path

from production import ProductionOwner, ROOT, free_loopback_port
from production_controls import ProductionApi, assert_scenario, inspect_download
from production_seed import provider_seed, seed_missions


def run(sha, evidence_root):
    if (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        != sha
    ):
        raise ValueError("Acceptance requires committed HEAD")
    owner = ProductionOwner(
        f"briefing-background-{sha[:10]}-{time.time_ns()}", evidence_root
    )
    context = owner.root / "candidate-source"
    archive = owner.root / "candidate.tar"
    owner.ownership["temporaryPaths"] += [str(context), str(archive)]
    owner.env.update(
        BRIEFING_SOURCE_ROOT=str(context),
        BRIEFING_PORT=str(free_loopback_port()),
        BRIEFING_ENABLED="true",
    )
    for name in ("backend", "frontend"):
        tag = f"briefing-background-{name}:{sha[:10]}-{owner.project.rsplit('-',1)[1]}"
        owner.env[f"BRIEFING_{name.upper()}_IMAGE"] = tag
        owner.ownership["images"].append(tag)
    summary = {"candidateSha": sha, "checksPassed": False, "project": owner.project}
    previous = {
        sig: signal.signal(sig, owner.signal) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    owner.persist()

    def python(code, timeout=120):
        return owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            code,
            timeout=timeout,
        ).splitlines()[-1]

    def records():
        return json.loads(
            python(
                "import json; from app.mission.slide_cache.store import default_store; c=default_store(); print(json.dumps({m:{l:{k:r[k] for k in ('token','state','fingerprint','warning')} for l,r in c.records(m).items()} for m in c.missions()}))"
            )
        )

    def wait_ready(mission=None, state=None):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            current = records()
            selected = (
                current.get(mission, {})
                if mission
                else {l: r for legs in current.values() for l, r in legs.items()}
            )
            if selected and all(
                r["state"] == (state or "ready") for r in selected.values()
            ):
                return current
            if any(r["state"] == "failed" for r in selected.values()):
                raise ValueError(
                    "Background preparation failed: " + json.dumps(current)
                )
            time.sleep(0.2)
        raise TimeoutError("Background preparation did not finish")

    try:
        owner.execute(
            ["git", "archive", "--format=tar", f"--output={archive}", sha], timeout=30
        )
        context.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(context, filter="data")
        owner.compose_file = (
            context / "tools/acceptance/customer-briefing/compose.production.yml"
        )
        owner.ownership["composeFile"] = str(owner.compose_file)
        for name, dockerfile, build_context in (
            ("backend", "backend/starlink-location/Dockerfile", context),
            (
                "frontend",
                "frontend/mission-planner/Dockerfile",
                context / "frontend/mission-planner",
            ),
        ):
            tag = owner.env[f"BRIEFING_{name.upper()}_IMAGE"]
            command = [
                "timeout",
                "--kill-after=10s",
                "30m",
                "docker",
                "build",
                "--no-cache",
                "-f",
                str(context / dockerfile),
                "--build-arg",
                f"ACCEPTANCE_CANDIDATE_SHA={sha}",
                "-t",
                tag,
            ]
            if ca := os.environ.get("CODEX_PROXY_CERT"):
                command += ["--secret", f"id=proxy_ca,src={ca}"]
            owner.execute([*command, str(build_context)], timeout=1815)
            actual = owner.execute(
                [
                    "docker",
                    "image",
                    "inspect",
                    tag,
                    "--format",
                    '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                ],
                timeout=30,
            ).strip()
            if actual != sha:
                raise ValueError("Image SHA mismatch")
        owner.compose(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "starlink-location",
            "python",
            "-c",
            provider_seed(),
            timeout=60,
        )
        owner.compose("up", "-d", "--wait", timeout=180)
        api = ProductionApi(owner)
        start = time.monotonic()
        saved = seed_missions(api, owner.root, names=["normal", "two-page", "five-leg"])
        initial = wait_ready()
        summary["initialPreparationSeconds"] = time.monotonic() - start
        timings = {}
        for case in saved:
            body, headers, elapsed = api.request(
                "POST",
                f"/api/v2/missions/{saved[case]['id']}/export",
                data={},
                timeout=660,
            )
            inspected = inspect_download(body, headers, "included")
            assert_scenario(case, inspected)
            target = owner.root / f"{case}.zip"
            target.write_bytes(body)
            timings[case] = {
                "readyExportSeconds": elapsed,
                "pageCount": inspected["pageCount"],
            }
            owner.compose(
                "cp", str(target), f"starlink-location:/tmp/{case}.zip", timeout=30
            )
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "/acceptance/production_pdf_probe.py",
                f"/tmp/{case}.zip",
                f"/tmp/{case}-inspection",
                timeout=180,
            )
            owner.compose(
                "cp",
                f"starlink-location:/tmp/{case}-inspection",
                str(owner.root / f"{case}-inspection"),
                timeout=30,
            )
            baseline = json.loads(
                python(
                    f"""import json,time,threading
from dataclasses import replace
from app.mission.slide_cache.store import default_store
from app.mission.slide_cache.identity import decode_snapshot
from app.mission.exporter.customer_runtime import render_customer_artifacts
from app.mission.storage import load_mission_v2
from app.mission.exporter.snapshot_inputs import canonical_json
mission=load_mission_v2({saved[case]['id']!r}); records=default_store().records(mission.id)
parts=[decode_snapshot(records[l.id]['snapshot']) for l in mission.legs]
snapshot=replace(parts[0],metadata_json=canonical_json(mission.model_dump(mode='json')),legs=tuple(p.legs[0] for p in parts),leg_number_offset=0,leg_count=None)
start=time.monotonic(); outcome=render_customer_artifacts(snapshot,cancel=threading.Event())
assert outcome.status=='included',outcome.warning_code
print(json.dumps({{'renderSeconds':time.monotonic()-start}}))
""",
                    timeout=120,
                )
            )
            timings[case].update(baseline)
        summary["timings"] = timings
        mission = saved["normal"]
        leg = dict(mission["legs"][0])
        # Hold the preparation lock briefly so even a fast machine observes an
        # actual owned worker before issuing the superseding save.
        owner.ownership["preparationGate"] = "/tmp/background-save-gate.json"
        owner.persist()
        owner.compose(
            "exec",
            "-d",
            "--user",
            "appuser",
            "starlink-location",
            "timeout",
            "--kill-after=5s",
            "40s",
            "python",
            "-c",
            """import json,time,os
from pathlib import Path
from filelock import FileLock
from app.mission.slide_cache.store import default_store
from app.mission.exporter.customer_runtime import _process_record
with FileLock(str(default_store().path.with_suffix('.worker.lock'))):
 Path('/tmp/background-save-gate.json').write_text(json.dumps(_process_record(os.getpid())))
 deadline=time.monotonic()+30
 while not Path('/tmp/background-save-gate.release').exists() and time.monotonic()<deadline: time.sleep(.05)
""",
            timeout=30,
        )
        for _ in range(50):
            gate = json.loads(
                python(
                    "import json; from pathlib import Path; p=Path('/tmp/background-save-gate.json'); print(p.read_text() if p.exists() else 'null')"
                )
            )
            if gate:
                break
            time.sleep(0.1)
        assert gate, "Preparation barrier did not acquire ownership"
        leg["adjusted_departure_time"] = "2026-10-25T14:01:00Z"
        _, _, save_seconds = api.request(
            "PUT", f"/api/v2/missions/{mission['id']}/legs/{leg['id']}", data=leg
        )
        running = wait_ready(mission["id"], "running")
        owned = json.loads(python("""import json; from pathlib import Path
from app.mission.exporter.customer_runtime import _process_record
records=[]
for path in Path('/proc').glob('[0-9]*/cmdline'):
 try:
  command=path.read_bytes()
  if b'app.mission.slide_cache.worker' in command and b'-c' not in command.split(b'\\0'):
   record=_process_record(int(path.parent.name))
   if record: records.append(record)
 except OSError: pass
print(json.dumps(records))
"""))
        leg["adjusted_departure_time"] = "2026-10-25T14:02:00Z"
        api.request(
            "PUT", f"/api/v2/missions/{mission['id']}/legs/{leg['id']}", data=leg
        )
        python(
            "from pathlib import Path; Path('/tmp/background-save-gate.release').touch(); print('released')"
        )
        final = wait_ready()
        assert (
            final[mission["id"]][leg["id"]]["token"]
            != running[mission["id"]][leg["id"]]["token"]
        )
        for other in ("two-page", "five-leg"):
            assert final[saved[other]["id"]] == initial[saved[other]["id"]]
        assert owned
        stopped = json.loads(
            python(
                f"from app.mission.exporter.customer_runtime import _alive; import json; print(json.dumps(all(not _alive(r) for r in {owned!r})))"
            )
        )
        assert stopped
        assert json.loads(
            python(
                f"from app.mission.exporter.customer_runtime import _alive; import json; print(json.dumps(not _alive({gate!r})))"
            )
        )
        summary["supersedingSave"] = {
            "saveSeconds": save_seconds,
            "oldWorkerReaped": stopped,
            "unrelatedArtifactsReused": True,
        }
        owner.compose("restart", "starlink-location", timeout=60)
        owner.compose("up", "-d", "--wait", timeout=180)
        recovered = wait_ready()
        assert recovered == final
        summary["restartReusesReadyPages"] = True
        browser_root = "/tmp/background-browser"
        owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "node",
            "/acceptance/production-journey.mjs",
            "http://mission-planner",
            saved["normal"]["name"],
            "included",
            browser_root,
            timeout=120,
        )
        owner.compose(
            "cp",
            f"starlink-location:{browser_root}",
            str(owner.root / "browser"),
            timeout=30,
        )
        final_body, headers, _ = api.request(
            "POST", f"/api/v2/missions/{mission['id']}/export", data={}
        )
        inspected = inspect_download(final_body, headers, "included")
        assert (
            inspected["evidence"]["legs"][0]["canonical"]["utcBounds"][0]
            == "2026-10-25T14:02:00Z"
        )
        summary["checksPassed"] = True
    finally:
        try:
            owner.cleaning = True
            if "BRIEFING_BACKEND_IMAGE" in owner.env:
                try:
                    owner.compose("logs", "--no-color", timeout=30)
                except (RuntimeError, OSError, TimeoutError):
                    pass
            owner.finalize_summary(summary)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            (owner.root / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.candidate_sha, args.evidence_root), indent=2))
