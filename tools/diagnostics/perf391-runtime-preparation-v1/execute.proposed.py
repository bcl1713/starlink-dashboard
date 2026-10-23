"""PROPOSAL ONLY. Separately authorize and review before invoking --execute.

This executor consumes the dry-run plan; it never builds or pulls images. A
supervising host timeout and post-timeout cleanup audit remain mandatory.
"""

import argparse
import asyncio
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time
import uuid

from prepare import REPO, check_release, sha, write, verify_overlay, browser_tree
from launcher import launch_plan, validate_receipt


async def execute(args):
    proposed = json.loads(args.launch_plan.read_bytes())
    receipt = json.loads(args.receipt.read_bytes())
    plan_path = args.build_plan.resolve()
    plan = json.loads(plan_path.read_bytes())
    verify_overlay(plan)
    validate_receipt(receipt, plan, sha(plan_path))
    launch = launch_plan(proposed["role"], proposed["root"], plan_path, receipt)
    if proposed != launch:
        raise ValueError("launch plan differs from reviewed built receipt plan")
    if not args.authorization.startswith(
        "https://github.com/bcl1713/starlink-dashboard/pull/408#"
    ):
        raise ValueError("separate explicit runtime checkpoint reference required")
    check_release()
    if sha(args.node) != receipt["browser"]["node_sha256"]:
        raise ValueError("actual Node executable hash differs")
    if (
        sha(receipt["browser"]["chromium_executable"])
        != receipt["browser"]["chromium_sha256"]
    ):
        raise ValueError("actual Chromium executable hash differs")
    if (
        browser_tree(
            receipt["browser"]["playwright_root"],
            receipt["browser"]["chromium_executable"],
        )
        != receipt["dependencies"]["browser_tree_sha256"]
    ):
        raise ValueError("actual Playwright/Chromium distribution differs")
    # Rehash each complete generated context before its first runtime use.
    import build

    context = Path(launch["env"]["PERF391_CONTEXT"])
    if (
        build.tree_manifest(context)["tree_sha256"]
        != plan["roles"][launch["role"]]["context_sha256"]
    ):
        raise ValueError("context drift")
    import fcntl

    lock_path = Path("/tmp/perf391-smoke-408.lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Port checking is not a durable reservation; bind failures later stop the run.
        for port in launch["ownership"]["ports"]:
            with socket.socket() as s:
                s.bind(("127.0.0.1", port))
        if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError("exclusive subreaper required")
        from owner import Owner
        from collector import prepare_collector
        import host

        owner = Owner(
            Path(launch["root"]),
            run=launch["env"]["PERF391_RUN"],
            sources={
                "build_plan_sha256": sha(plan_path),
                "receipt_sha256": sha(args.receipt),
                "authorization": args.authorization,
            },
            adopt_descendants=True,
        )
        owner.manifest.update(
            compose_project=launch["project"],
            volumes=launch["ownership"]["volumes"],
            networks=launch["ownership"]["networks"],
            listeners=launch["ownership"]["ports"],
            resource_intent=launch["ownership"],
        )
        owner.persist()
        root = owner.root
        verification_owner = Owner(
            root / "verification-owner",
            run=launch["env"]["PERF391_RUN"],
            sources=owner.manifest["sources"],
            adopt_descendants=True,
        )
        process_owner = verification_owner
        root = owner.root
        write(root / "launch.json", launch)
        write(root / "compose.base.json", launch["compose"]["base"])
        write(root / "compose.override.json", launch["compose"]["override"])
        write(root / "browser-options.json", launch["browser_options"])
        (root / "tmp").mkdir()
        (root / "backend").mkdir()
        env = {**os.environ, **launch["env"], "TMPDIR": str(root / "tmp")}
        began = time.monotonic()
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        dc = [
            "docker",
            "compose",
            "-p",
            launch["project"],
            "-f",
            str(root / "compose.base.json"),
            "-f",
            str(root / "compose.override.json"),
        ]
        command_count = 0

        async def command(argv, cap, *, cleanup=False):
            nonlocal command_count
            if not cleanup and (stop.is_set() or time.monotonic() - began >= 78):
                raise RuntimeError("work deadline or signal")
            command_count += 1
            log_path = root / ("command-%02d.log" % command_count)
            with log_path.open("wb") as log:
                child = process_owner.spawn(argv, stdout=log, env=env)
                limit = min(
                    cap, max(0.01, (90 if cleanup else 78) - (time.monotonic() - began))
                )
                until = time.monotonic() + limit
                while child.poll() is None:
                    if time.monotonic() >= until or (stop.is_set() and not cleanup):
                        # Owner.close owns signalling/reaping; do not start another command.
                        raise TimeoutError("command deadline/signal: " + str(argv[:3]))
                    if log_path.stat().st_size > 1048576:
                        raise RuntimeError("command log budget")
                    await asyncio.sleep(0.02)
                if child.returncode:
                    raise RuntimeError("command failure: " + str(argv[:3]))
            return log_path.read_text()

        failed = None
        host_job = None
        extraction_container = launch["project"] + "-assets"
        try:
            actual_node_version = (
                (await command([str(args.node), "--version"], 2))
                .strip()
                .removeprefix("v")
            )
            if actual_node_version != receipt["browser"]["node_version"]:
                raise ValueError("actual Node version differs")
            # Verify the immutable IDs and all expected labels through the selected daemon.
            for kind, image in receipt["images"].items():
                raw = await command(
                    [
                        "docker",
                        "image",
                        "inspect",
                        image["id"],
                        "--format",
                        "{{json .}}",
                    ],
                    2,
                )
                actual = json.loads(raw)
                if actual["Id"] != image["id"] or any(
                    actual["Config"]["Labels"].get(k) != v
                    for k, v in plan["roles"][launch["role"]]["labels"].items()
                ):
                    raise ValueError("daemon image differs from receipt: " + kind)
            # A stopped, labelled, task-owned container binds the asset bytes to the image ID.
            # It is never started and belongs to the verification Owner's intent.
            verification_owner.manifest.update(
                containers=[extraction_container], compose_project=launch["project"]
            )
            verification_owner.persist()
            await command(
                [
                    "docker",
                    "create",
                    "--name",
                    extraction_container,
                    "--label",
                    "com.docker.compose.project=" + launch["project"],
                    receipt["images"]["frontend"]["id"],
                ],
                2,
            )
            (root / "image-assets").mkdir()
            await command(
                [
                    "docker",
                    "cp",
                    extraction_container + ":/usr/share/nginx/html/.",
                    str(root / "image-assets"),
                ],
                3,
            )
            extracted = {**receipt, "asset_root": str(root / "image-assets")}
            validate_receipt(extracted, plan, sha(plan_path))
            await command(["docker", "rm", extraction_container], 2)
            await verification_owner.close()
            process_owner = owner
            for step in launch["commands"]:
                if step["phase"] in ("cleanup", "browser-and-source"):
                    continue
                if step["phase"] == "stop-backend":
                    # Browser/source work is explicitly inserted before this phase.
                    collector = prepare_collector(root / "host-collector", REPO)
                    pids = []
                    cgroups = []
                    mappings = []
                    for service in (
                        "starlink-location",
                        "prometheus",
                        "mission-planner",
                    ):
                        cid = (await command([*dc, "ps", "-q", service], 1)).strip()
                        row = json.loads(
                            await command(
                                [
                                    "docker",
                                    "inspect",
                                    cid,
                                    "--format",
                                    "{{json .State}}",
                                ],
                                1,
                            )
                        )
                        pid = int(row["Pid"])
                        if not row["Running"] or not Path(f"/proc/{pid}/stat").exists():
                            raise ValueError("host/container PID mapping unavailable")
                        membership = Path(f"/proc/{pid}/cgroup").read_text().strip()
                        if not membership.startswith("0::/"):
                            raise ValueError("cgroup v2 mapping required")
                        group = Path("/sys/fs/cgroup") / membership[3:].lstrip("/")
                        if not group.is_dir():
                            raise ValueError("host cgroup path unavailable")
                        pids.append(pid)
                        cgroups.append(group)
                        mappings.append(
                            {
                                "container": cid,
                                "host_pid": pid,
                                "cgroup": str(group),
                                "host_start_id": Path(f"/proc/{pid}/stat")
                                .read_text()
                                .rsplit(")", 1)[1]
                                .split()[19],
                                "status": Path(f"/proc/{pid}/status").read_text(),
                                "pid_namespace": os.readlink(f"/proc/{pid}/ns/pid"),
                            }
                        )
                    write(root / "host-mapping.json", mappings)
                    owner.manifest["containers"] = mappings
                    owner.persist()
                    browser_step = next(
                        s
                        for s in launch["commands"]
                        if s["phase"] == "browser-and-source"
                    )
                    argv = [str(args.node), *browser_step["argv"][1:]]
                    log = (root / "browser.log").open("wb")
                    browser_child = owner.spawn(argv, stdout=log, env=env)
                    pids.append(browser_child.pid)
                    host_bytes = 0
                    host_summary = None

                    async def emit(row):
                        nonlocal host_bytes, host_summary
                        registration = root / "browser/browser-process.json"
                        if registration.exists() and len(pids) == 4:
                            browser = json.loads(registration.read_bytes())
                            if (
                                Path(f"/proc/{browser['pid']}/stat")
                                .read_text()
                                .rsplit(")", 1)[1]
                                .split()[19]
                                != browser["start_id"]
                            ):
                                raise ValueError("browser host identity changed")
                            pids.append(browser["pid"])
                        if row.get("kind") == "summary":
                            host_summary = row
                        raw = (json.dumps(row) + "\n").encode()
                        host_bytes += len(raw)
                        if host_bytes > 67108864:
                            raise RuntimeError("host evidence budget")
                        with (root / "host.jsonl").open("ab") as f:
                            f.write(raw)

                    host_job = asyncio.create_task(
                        host.observe_resources(
                            collector,
                            emit,
                            clock_id="host/" + str(uuid.uuid4()),
                            pids=pids,
                            cgroups=cgroups,
                            samples=5,
                        )
                    )
                    try:
                        until = min(began + 78, time.monotonic() + 35)
                        while browser_child.poll() is None:
                            if stop.is_set() or time.monotonic() >= until:
                                raise TimeoutError("browser deadline or signal")
                            if host_job.done() and host_job.exception():
                                raise host_job.exception()
                            await asyncio.sleep(0.02)
                        if browser_child.returncode:
                            raise RuntimeError("browser smoke failure")
                        await asyncio.wait_for(
                            host_job, timeout=max(0.01, began + 78 - time.monotonic())
                        )
                        if (
                            host_summary is None
                            or host_summary["completed"] != 5
                            or host_summary["skipped"]
                            or not host_summary["complete"]
                        ):
                            raise RuntimeError("host final sample/loss gate")
                    finally:
                        log.close()
                argv = [
                    (
                        str(int(time.time()) - 20)
                        if v == "FUTURE_UTC_SECONDS_MINUS_20"
                        else v
                    )
                    for v in step["argv"]
                ]
                if step["phase"] == "seed-file":
                    argv[0] = sys.executable
                await command(argv, step["seconds"])
            stats = json.loads((root / "backend/backend-stats.json").read_bytes())
            if not stats.get("runtime_boundary_drained") or any(
                stats.get(k)
                for k in (
                    "buffered",
                    "dropped",
                    "invalid",
                    "failures",
                    "token_evictions",
                    "token_unavailable",
                )
            ):
                raise RuntimeError("backend drain/loss gate")
        except BaseException as error:
            failed = type(error).__name__ + ": " + str(error)[:512]
        finally:
            if host_job and not host_job.done():
                host_job.cancel()
                await asyncio.gather(host_job, return_exceptions=True)
            await verification_owner.close()
            # First reap command/browser groups; then a fresh bounded teardown command.
            await owner.close()
            # Owner is now closed, so use a separate cleanup Owner with the same resource intent.
            cleanup_owner = Owner(
                root / "cleanup-owner",
                run=launch["env"]["PERF391_RUN"],
                sources=owner.manifest["sources"],
                adopt_descendants=True,
            )
            cleanup_owner.manifest.update(
                compose_project=launch["project"],
                volumes=launch["ownership"]["volumes"],
                networks=launch["ownership"]["networks"],
            )
            cleanup_owner.persist()
            cleanup_error = None
            try:
                # Remove the stopped extraction container if interrupted before its normal rm.
                # Existence check and removal are scoped to the recorded name/project.
                with (root / "extraction-cleanup.log").open("wb") as f:
                    child = cleanup_owner.spawn(
                        [
                            "docker",
                            "ps",
                            "-aq",
                            "--filter",
                            "name=^/" + extraction_container + "$",
                            "--filter",
                            "label=com.docker.compose.project=" + launch["project"],
                        ],
                        stdout=f,
                        env=env,
                    )
                    await asyncio.wait_for(asyncio.to_thread(child.wait), timeout=2)
                    if child.returncode:
                        raise RuntimeError("extraction inventory failed")
                if (root / "extraction-cleanup.log").read_text().strip():
                    child = cleanup_owner.spawn(
                        ["docker", "rm", extraction_container], env=env
                    )
                    await asyncio.wait_for(asyncio.to_thread(child.wait), timeout=2)
                    if child.returncode:
                        raise RuntimeError("extraction cleanup failed")
                with (root / "compose-down.log").open("wb") as f:
                    child = cleanup_owner.spawn(
                        [
                            *dc,
                            "down",
                            "--volumes",
                            "--remove-orphans",
                            "--timeout",
                            "2",
                        ],
                        stdout=f,
                        env=env,
                    )
                    await asyncio.wait_for(asyncio.to_thread(child.wait), timeout=10)
                    if child.returncode:
                        raise RuntimeError("compose teardown failed")
            except BaseException as error:
                cleanup_error = type(error).__name__
            finally:
                await cleanup_owner.close()
            write(
                root / "runtime-result.json",
                {
                    "failure": failed,
                    "cleanup_error": cleanup_error,
                    "owner_status": owner.manifest["status"],
                    "external_host_audit_required": True,
                },
            )
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
        if failed or cleanup_error or owner.manifest["status"] != "clean":
            raise RuntimeError(
                "runtime/cleanup failed; inspect retained evidence and audit before any C run"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-plan", type=Path, required=True)
    parser.add_argument("--build-plan", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error(
            "proposal: use launcher.py for offline dry-run; runtime execution requires separate authorization"
        )
    asyncio.run(execute(args))
