"""Preserve public job failures before owned runtime teardown."""

import json
import runpy
from pathlib import Path

import pytest

ENTRY = (
    Path(__file__).resolve().parents[2]
    / "tools/acceptance/pop-transitions/download_evidence.py"
)


def test_failed_public_preparation_retains_exact_job_before_teardown(tmp_path):
    value = runpy.run_path(str(ENTRY))
    job = {"id": "job1", "state": "failed", "error_code": "pdf", "warning_code": "pdf"}

    class Api:
        def request(self, method, path):
            return json.dumps(job).encode(), {"Content-Type": "application/json"}, 0.1

    def download(api, mission_id, **kwargs):
        api.request("GET", f"/api/v2/missions/{mission_id}/export-preparations/job1")
        raise ValueError("Export preparation did not become ready")

    with pytest.raises(ValueError, match="did not become ready"):
        value["download_with_evidence"](Api(), "mission", tmp_path, download)
    report = json.loads((tmp_path / "public-preparation-responses.json").read_text())
    assert report[0]["body"] == job
    assert report[0]["method"] == "GET"
    assert "did not become ready" in (tmp_path / "preparation-failure.json").read_text()


def test_omitted_download_preserves_warning_headers_and_exact_zip(tmp_path):
    value = runpy.run_path(str(ENTRY))
    headers = {
        "X-Customer-Briefing-Status": "omitted",
        "X-Customer-Briefing-Warning": "overflow",
    }

    def download(api, mission_id, **kwargs):
        return b"archived exact ZIP", headers, 1.5, [{"state": "ready"}]

    result = value["download_with_evidence"](object(), "mission", tmp_path, download)
    assert result[0] == (tmp_path / "download.zip").read_bytes()
    assert json.loads((tmp_path / "download-headers.json").read_text()) == headers
