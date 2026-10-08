"""Application staging, paired qualification and real emergency process cleanup."""

import importlib
import json
import sys
import threading
from hashlib import sha256
from pathlib import Path

import psutil
import pytest

from tests.unit.test_customer_evidence import mission_case


def implementation():
    name = "app.mission.exporter.customer_runtime"
    assert importlib.util.find_spec(name), "Application-owned renderer contract absent"
    return importlib.import_module(name)


def stage_report(module, monkeypatch, tmp_path, mutate=lambda report: None):
    captured, _payload, _plan, report = mission_case()
    pdf = b"%PDF-qualified-test-control"
    report["artifacts"] = {"pdfPath": "mission-customer-briefing-trial.pdf"}
    report["artifactHashes"]["pdfPath"] = sha256(pdf).hexdigest()
    report["cleanup"].update(
        contextsClosed=True,
        browserExited=True,
        listenerClosed=True,
        childrenReaped=True,
        survivors=[],
        errors=[],
    )
    mutate(report)
    roots = []

    def run(command, staging, *, cancel, **kwargs):
        roots.append(Path(staging))
        (Path(staging) / "mission-customer-briefing-trial.pdf").write_bytes(pdf)
        (Path(staging) / "render-report.json").write_text(json.dumps(report))
        return 0

    monkeypatch.setattr(module, "run_owned_renderer", run)
    monkeypatch.setattr(module, "STAGING_PARENT", tmp_path)
    return captured, roots, pdf


def test_qualified_pair_has_captured_identity_and_no_private_paths(
    monkeypatch, tmp_path
):
    module = implementation()
    captured, roots, pdf = stage_report(module, monkeypatch, tmp_path)
    result = module.render_customer_artifacts(captured, cancel=threading.Event())
    assert result.status == "included"
    assert result.artifacts.pdf == pdf
    evidence = json.loads(result.artifacts.evidence)
    assert evidence["snapshotFingerprint"] == captured.fingerprint
    assert evidence["schemaVersion"] == 2
    assert str(tmp_path) not in result.artifacts.evidence.decode()
    assert all(not root.exists() for root in roots)


@pytest.mark.parametrize(
    "case,code",
    [
        ("identity", "evidence"),
        ("hash", "pdf"),
        ("row", "evidence"),
        ("late", "deadline"),
        ("cleanup", "cleanup"),
    ],
)
def test_unqualified_report_omits_both_and_removes_staging(
    monkeypatch, tmp_path, case, code
):
    module = implementation()

    def mutate(report):
        if case == "identity":
            report["snapshotFingerprint"] = "wrong"
        if case == "hash":
            report["artifactHashes"]["pdfPath"] = "0" * 64
        if case == "row":
            report["pdfValidation"]["rows"][0]["displayCells"][0] = "wrong"
        if case == "late":
            report["totalMs"] = 60001
        if case == "cleanup":
            report["cleanup"]["childrenReaped"] = False

    captured, roots, _ = stage_report(module, monkeypatch, tmp_path, mutate)
    result = module.render_customer_artifacts(captured, cancel=threading.Event())
    assert result.status == "omitted"
    assert result.warning_code == code
    assert result.artifacts is None
    assert all(not root.exists() for root in roots)


def test_emergency_deadline_stops_recorded_detached_child_before_return(tmp_path):
    module = implementation()
    script = tmp_path / "hung-renderer.py"
    script.write_text("""import json, os, signal, subprocess, sys, time
from pathlib import Path
root=Path(sys.argv[1])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child=subprocess.Popen([sys.executable,"-c","import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(3600)"],start_new_session=True)
def start(pid):return Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()[19]
(root/"ownership.json").write_text(json.dumps({"pid":os.getpid(),"start":start(os.getpid()),"browserPid":child.pid,"browserPgid":child.pid,"browserStart":start(child.pid),"workers":[]}))
(root/"child-pid").write_text(str(child.pid))
time.sleep(3600)
""")
    with pytest.raises(module.RendererFailure) as failure:
        module.run_owned_renderer(
            [sys.executable, str(script), str(tmp_path)],
            tmp_path,
            cancel=threading.Event(),
            wall_seconds=0.3,
            kill_grace_seconds=0.2,
        )
    assert failure.value.code == "deadline"
    owner = json.loads((tmp_path / "python-owner.json").read_text())
    assert owner["reaped"] is True
    assert owner["cleanup"]["survivors"] == []
    child = int((tmp_path / "child-pid").read_text())
    assert (
        not psutil.pid_exists(child)
        or psutil.Process(child).status() == psutil.STATUS_ZOMBIE
    )


def test_cancelled_real_renderer_is_reaped_and_no_pair_is_returned(tmp_path):
    module = implementation()
    cancel = threading.Event()
    timer = threading.Timer(0.15, cancel.set)
    timer.start()
    try:
        with pytest.raises(module.ExportCancelled):
            module.run_owned_renderer(
                [sys.executable, "-c", "import time; time.sleep(3600)"],
                tmp_path,
                cancel=cancel,
                wall_seconds=2,
                kill_grace_seconds=0.2,
            )
    finally:
        timer.cancel()
        timer.join()
    owner = json.loads((tmp_path / "python-owner.json").read_text())
    assert owner["reaped"] is True and owner["cleanup"]["survivors"] == []


def test_blocked_cleanup_retains_ownership_evidence_without_publishing_pair(
    monkeypatch, tmp_path
):
    module = implementation()
    captured, roots, _ = stage_report(module, monkeypatch, tmp_path)

    def blocked(command, staging, **kwargs):
        roots.append(Path(staging))
        (Path(staging) / "python-owner.json").write_text(
            json.dumps(
                {
                    "pid": 123,
                    "reaped": False,
                    "cleanup": {"survivors": [123]},
                }
            )
        )
        raise module.RendererFailure("cleanup")

    monkeypatch.setattr(module, "run_owned_renderer", blocked)
    result = module.render_customer_artifacts(captured, cancel=threading.Event())
    assert result.warning_code == "cleanup" and result.artifacts is None
    assert roots[0].exists() and (roots[0] / "python-owner.json").exists()
