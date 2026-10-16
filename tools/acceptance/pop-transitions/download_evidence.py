"""Persist public preparation responses before runtime owners remove resources."""

import json


def download_with_evidence(api, mission_id, destination, download):
    responses = []

    class RecordingApi:
        def request(self, method, path, *args, **kwargs):
            content, headers, seconds = api.request(method, path, *args, **kwargs)
            if not path.endswith("/download"):
                responses.append(
                    {
                        "method": method,
                        "path": path,
                        "headers": dict(headers),
                        "body": json.loads(content),
                    }
                )
                (destination / "public-preparation-responses.json").write_text(
                    json.dumps(responses, indent=2)
                )
            return content, headers, seconds

    try:
        result = download(RecordingApi(), mission_id, timeout=600)
    except Exception as error:  # Persist diagnostic, then propagate unchanged.
        (destination / "preparation-failure.json").write_text(
            json.dumps({"errorType": type(error).__name__, "error": str(error)})
        )
        raise
    content, headers, _seconds, stages = result
    (destination / "download.zip").write_bytes(content)
    (destination / "download-headers.json").write_text(
        json.dumps(dict(headers), indent=2)
    )
    (destination / "preparation-stages.json").write_text(json.dumps(stages, indent=2))
    return result
