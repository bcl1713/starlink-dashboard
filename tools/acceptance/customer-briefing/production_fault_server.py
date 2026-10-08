"""Isolated acceptance failure boundaries around the unchanged production API."""

import json
import os
import sys
import zipfile


def install(fault):
    original_decode, original_write = json.loads, zipfile.ZipFile.writestr

    def decode(content, *args, **kwargs):
        value = original_decode(content, *args, **kwargs)
        if (
            fault in {"pdf", "evidence"}
            and isinstance(value, dict)
            and value.get("schemaVersion") == 2
            and value.get("status") == "success"
            and value.get("sharedBrowser") is True
            and "artifactHashes" in value
        ):
            if fault == "pdf":
                value["artifactHashes"]["pdfPath"] = "0" * 64
            else:
                value["snapshotFingerprint"] = "0" * 64
            print(
                json.dumps(
                    {"acceptanceFaultBoundary": "render-report-decode", "fault": fault}
                ),
                file=sys.stderr,
                flush=True,
            )
        return value

    def write(archive, name, *args, **kwargs):
        filename = name.filename if isinstance(name, zipfile.ZipInfo) else name
        if (
            fault == "publication"
            and filename == "exports/mission/mission-customer-briefing-evidence.json"
        ):
            print(
                json.dumps(
                    {
                        "acceptanceFaultBoundary": "optional-evidence-zip-write",
                        "fault": fault,
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
            raise OSError("Isolated acceptance ZIP write failure")
        return original_write(archive, name, *args, **kwargs)

    if fault in {"pdf", "evidence"}:
        json.loads = decode
    elif fault == "publication":
        zipfile.ZipFile.writestr = write
    elif fault:
        raise ValueError("Unsupported acceptance fault")

    def restore():
        json.loads, zipfile.ZipFile.writestr = original_decode, original_write

    return restore


if __name__ == "__main__":
    import uvicorn

    restore = install(os.environ.get("BRIEFING_APP_FAULT", ""))
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000)
    finally:
        restore()
