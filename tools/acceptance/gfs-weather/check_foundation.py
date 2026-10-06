"""Production Nginx/worker controls with independent dated source oracles."""

import concurrent.futures
import hashlib
import json
import struct
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:15292"


def request(path, data=None, headers=None):
    headers = {**(headers or {})}
    if data is not None:
        headers["Content-Type"] = "application/json"
    started = time.monotonic()
    req = urllib.request.Request(
        API + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method="PUT" if data is not None else "GET",
    )
    try:
        response = urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return (
            response.status,
            response.headers,
            response.read(),
            time.monotonic() - started,
        )


def wait(operation, seconds=40):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = operation()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError("Foundation control timed out")


def run(check):
    output = check.output
    control_path = output / "control/control.json"
    base = {"replay_utc_ms": 1791288447620, "frame": 1791288327}

    def control(**values):
        temporary = control_path.with_suffix(".new")
        temporary.write_text(json.dumps({**base, **values}))
        temporary.replace(control_path)
        control_path.chmod(0o666)

    def catalog():
        status, _, body, _ = request("/api/aviation-weather/v1/catalog")
        assert status == 200
        return {p["layer_id"]: p for p in json.loads(body)["products"]}

    def enabled():
        result = request(
            "/api/aviation-weather/v1/settings",
            {
                "winds": True,
                "temperature": True,
            },
        )
        assert result[0] == 200
        return json.loads(result[2])

    def disabled():
        result = request(
            "/api/aviation-weather/v1/settings",
            {
                "winds": False,
                "temperature": False,
            },
        )
        assert result[0] == 200 and result[3] < 15
        settings = json.loads(result[2])
        ack = check.worker_json("/app/data/gfs-mailbox/ack.json")
        owner = check.worker_json("/app/data/gfs-mailbox/worker.json")
        assert (
            ack["revision"] == settings["revision"] and ack["owner"] == owner["owner"]
        )
        return result[3]

    def quota_ready():
        budget = check.worker_json("/app/data/gfs-mailbox/budget.json", missing={})
        attempts = budget.get("attempts", [])
        if attempts:
            # Give the persistent production attempt budget a full minute.
            time.sleep(61)

    def blocked():
        catalog()
        path = output / "control/blocked-decoder.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    def no_child(pid):
        return (
            check.worker_command(
                [
                    "python",
                    "-c",
                    "import os,sys;sys.exit(os.path.exists('/proc/'+sys.argv[1]))",
                    str(pid),
                ],
                allow_failure=True,
            ).returncode
            == 0
        )

    def deny_all():
        products = catalog()
        assert all(
            products[k]["state"] in {"off", "unavailable"}
            for k in ("gfs-winds", "gfs-temperature")
        )
        assert all(request(path)[0] == 404 for path in old_paths)

    control()
    enabled()

    def admitted():
        product = catalog()["gfs-winds"]
        return product if product["state"] in {"ready", "stale"} else None

    product = wait(admitted)
    temp = catalog()["gfs-temperature"]
    assert temp["instance_id"] != product["instance_id"]
    old_paths = [product["payload"]["path"], temp["payload"]["path"]]
    status, headers, body, _ = request(old_paths[0])
    assert (
        status == 200
        and hashlib.sha256(body).hexdigest() == product["payload"]["sha256"]
    )
    assert request(old_paths[0], headers={"If-None-Match": headers["ETag"]})[0] == 304
    grid = json.loads(body)
    assert grid["mask_scope"] == "shared-conservative-uvt"
    assert grid["run_at_ms"] == 1791244800000 and grid["lead_seconds"] == 21600
    buffers = {}
    for name, descriptor in grid["buffers"].items():
        status, _, body, _ = request(descriptor["path"])
        assert status == 200 and len(body) == descriptor["byte_length"]
        assert hashlib.sha256(body).hexdigest() == descriptor["sha256"]
        buffers[name] = body
        old_paths.append(descriptor["path"])
        (output / f"{name}.bin").write_bytes(body)
    masks = buffers["mask"]
    assert len(masks) == 720 * 361 and set(masks) <= {0, 1, 2}
    assert 0 < sum(value != 0 for value in masks) < len(masks)
    samples = []
    for oracle in json.loads((output / "capture/gfs/oracles.json").read_bytes()):
        row = round((90 - oracle["latitude"]) / 0.5)
        col = round((oracle["longitude"] + 180) / 0.5) % 720
        index = row * 720 + col
        assert masks[index] == 0
        values = {
            name: struct.unpack_from("<h", buffers[name], 2 * index)[0] * 0.01
            + (273.15 if name == "t" else 0)
            for name in ("u", "v", "t")
        }
        errors = {
            name: abs(values[name] - oracle["source_values"][name]) for name in values
        }
        assert max(errors.values()) <= 0.01
        samples.append({**oracle, "normalized": values, "errors": errors})
    (output / "samples.json").write_text(json.dumps(samples, indent=2))
    decode_metrics = [
        json.loads(line)
        for line in (output / "control/decoder-metrics.jsonl").read_text().splitlines()
    ]
    assert decode_metrics and all(
        m["successful_decode"] and m["wall_seconds"] < 60 for m in decode_metrics
    )
    check.proofs.update(successful_decode=True, nginx_buffers=True, source_oracles=True)
    check.proofs["disable_ack"] = disabled() < 15
    deny_all()

    # Saturation/failure leave unrelated controls responsive through Nginx.
    quota_ready()
    control(gfs_block_decode=True)
    enabled()
    child = wait(blocked)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        controls = list(pool.map(request, ["/api/status"] * 32))
    assert all(result[0] == 200 and result[3] < 2 for result in controls)
    (output / "core-latencies.json").write_text(json.dumps([v[3] for v in controls]))
    assert disabled() < 15
    wait(lambda: no_child(child["pid"]))
    deny_all()
    check.proofs.update(cancelled_decoder=True, core_health=True, disabled_denial=True)
    (output / "control/blocked-decoder.json").unlink()

    quota_ready()
    control(gfs_block_decode=True)
    enabled()
    child = wait(blocked)
    check.worker_command(
        [
            "python",
            "-c",
            "import os,signal,sys; p=int(sys.argv[1]); assert b'/acceptance/decoder_fixture.py' in open('/proc/'+str(p)+'/cmdline','rb').read(); os.kill(p,signal.SIGKILL)",
            str(child["pid"]),
        ]
    )
    wait(lambda: no_child(child["pid"]))
    assert disabled() < 15
    deny_all()
    check.proofs["killed_decoder_denial"] = True
    (output / "control/blocked-decoder.json").unlink()

    quota_ready()
    control(gfs_mismatch=True)
    before = len((output / "control/gfs-events.jsonl").read_text().splitlines())
    enabled()

    def mismatch():
        catalog()
        events = [
            json.loads(line)
            for line in (output / "control/gfs-events.jsonl")
            .read_text()
            .splitlines()[before:]
        ]
        return any(event.get("etag") == '"different-version"' for event in events)

    wait(mismatch)
    time.sleep(1)
    assert len(
        (output / "control/decoder-metrics.jsonl").read_text().splitlines()
    ) == len(decode_metrics)
    assert disabled() < 15
    deny_all()
    check.proofs["version_mismatch"] = True
    check.proofs["decoder_metrics"] = decode_metrics
    control()
