"""Qualify actual route/airport pixels and their scene/marker identity."""

import json
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def pixels(image):
    # Pillow's new accessor is optional in the packaged older renderer runtime.
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter is not None else image.getdata()


def scene_digest(scene, *, node="node"):
    # Use the renderer's JSON.stringify representation, including JS number encoding.
    command = "const fs=require('fs'),c=require('crypto');const s=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(c.createHash('sha256').update(JSON.stringify(s)).digest('hex'))"
    return subprocess.check_output(
        [node, "-e", command], input=json.dumps(scene).encode(), timeout=10
    ).decode()


def verify_rendered_map(
    path,
    stage,
    *,
    leg_id,
    expected_digest,
    expected_marker_ids,
    resampled=False,
    stationary=False,
):
    if stage.get("status") != "primary":
        raise ValueError("Map stage did not produce a primary rendered scene")
    if (
        not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        or stage.get("inputDigest") != expected_digest
    ):
        raise ValueError("Map scene identity does not match the captured source")
    if {marker["id"] for marker in stage.get("markers", [])} != set(
        expected_marker_ids
    ):
        raise ValueError("Rendered window marker identities do not match the scene")
    raw = Path(path).read_bytes()
    if (
        not resampled
        and stage.get("pngHash")
        and sha256(raw).hexdigest() != stage["pngHash"]
    ):
        raise ValueError("Rendered map image identity does not match its stage")
    with Image.open(path) as source:
        image = source.convert("RGB")
    width, height = image.size
    viewport = stage.get("viewport") or {}
    vw, vh = viewport.get("width"), viewport.get("height")
    if width < 320 or height < 240 or not vw or not vh:
        raise ValueError("Rendered map dimensions are unusable")
    if not resampled and (width, height) != (vw, vh):
        raise ValueError("Rendered map dimensions do not match its stage")
    if resampled and abs(width / height - vw / vh) > 0.02:
        raise ValueError("Rendered map aspect does not match its stage")
    # The deployed route core is #ffd86b with #ffb000 glow. Country borders
    # and the basemap are neutral/blue; they cannot satisfy this orange mask.
    positions = [
        index
        for index, (r, g, b) in enumerate(pixels(image))
        if r >= 150 and g >= 80 and b <= 180 and r - g >= 15 and r - b >= 75
    ]
    if not stationary and len(positions) < 50:
        raise ValueError("Route overlay pixels are absent from the rendered basemap")
    endpoints = stage.get("endpoints", [])
    if {point["role"] for point in endpoints} != {"departure", "arrival"}:
        raise ValueError("Departure/arrival overlay metadata is incomplete")
    radius = max(8, round(width / 280 * 8))
    verified_endpoints = 0
    for point in endpoints:
        x, y = round(point["x"] * width / vw), round(point["y"] * height / vh)
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError("Endpoint overlay is outside the map viewport")
        region = image.crop(
            (
                max(0, x - radius),
                max(0, y - radius),
                min(width, x + radius + 1),
                min(height, y + radius + 1),
            )
        )
        white = sum(r >= 220 and g >= 220 and b >= 210 for r, g, b in pixels(region))
        if white < 10:
            raise ValueError("Expected airport overlay pixels are missing")
        verified_endpoints += 1
    bbox = (
        [
            min(i % width for i in positions),
            min(i // width for i in positions),
            max(i % width for i in positions),
            max(i // width for i in positions),
        ]
        if positions
        else None
    )
    return {
        "leg_id": leg_id,
        "stage": stage["status"],
        "width": width,
        "height": height,
        "scene_hash": expected_digest,
        "window_marker_count": len(expected_marker_ids),
        "route_overlay_pixels": len(positions),
        "route_overlay_bbox": bbox,
        "endpoint_overlays": verified_endpoints,
        "pixel_sha256": sha256(image.tobytes()).hexdigest(),
    }


def inspect_pdf_maps(pdf, evidence, output, scenes):
    """Inspect the map XObject on each leg's own PDF page, never another leg's image."""
    output = Path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    render = evidence["render"]
    maps = render.get("maps") or {evidence["legId"]: render["map"]}
    pages = evidence.get("pages") or [{"page": 1, "legId": evidence["legId"]}]
    results = []
    reader = PdfReader(pdf)
    for number, (leg_id, scene) in enumerate(scenes.items(), 1):
        stage = maps[leg_id]
        if scene is None or stage.get("status") != "primary":
            raise ValueError("A canonical leg did not render a primary customer map")
        measured = render.get("fit", {}).get("pages", [])
        candidates = [
            page["page"]
            for page in pages
            if page.get("legId", evidence.get("legId")) == leg_id
            and (not measured or measured[page["page"] - 1].get("mapPlacement"))
        ]
        if not candidates:
            raise ValueError("Customer map has no identified PDF page")
        page = candidates[0]
        viewport = stage["viewport"]
        images = []
        for index, embedded in enumerate(reader.pages[page - 1].images):
            if embedded.image.size == (viewport["width"], viewport["height"]):
                path = output / f"leg-{number}-page-{page}-{index}.png"
                embedded.image.save(path)
                images.append(path)
        if len(images) != 1:
            raise ValueError(
                "PDF page does not contain exactly one map image matching its stage"
            )
        stationary = (
            len({(point["latitude"], point["longitude"]) for point in scene["route"]})
            == 1
        )
        proof = verify_rendered_map(
            images[0],
            stage,
            leg_id=leg_id,
            expected_digest=scene_digest(scene),
            expected_marker_ids=[marker["id"] for marker in scene["markers"]],
            resampled=True,
            stationary=stationary,
        )
        proof.update(page=page, image=images[0].name)
        results.append(proof)
    (output / "map-pixel-proof.json").write_text(json.dumps(results, indent=2))
    return results
