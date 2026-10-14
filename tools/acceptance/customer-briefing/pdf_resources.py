"""Independent recursive inventory of reachable images, including soft masks."""

import io
import json
from hashlib import sha256

from pypdf import PdfReader
from pypdf.generic import IndirectObject, StreamObject


def _semantic(value, active=None):
    """Resolve dependencies before hashing; PDF object numbers are not identity."""
    active = set() if active is None else active
    if isinstance(value, IndirectObject):
        value = value.get_object()
    if isinstance(value, (dict, list)):
        key = id(value)
        if key in active:
            return {"cycle": True}
        active = active | {key}
        if isinstance(value, dict):
            result = {
                str(k): _semantic(v, active)
                for k, v in sorted(value.items())
                if str(k) not in {"/Length", "/Filter", "/DecodeParms"}
            }
            if isinstance(value, StreamObject):
                result["pixelsHash"] = sha256(value.get_data()).hexdigest()
            return result
        return [_semantic(v, active) for v in value]
    if isinstance(value, bytes):
        return {"bytesHash": sha256(value).hexdigest()}
    return str(value)


def image_inventory(pdf_bytes: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    found = {}

    def visit(ref, page, active):
        obj = ref.get_object()
        key = (
            (ref.idnum, ref.generation)
            if isinstance(ref, IndirectObject)
            else (id(obj), 0)
        )
        if key in active:
            return
        active = active | {key}
        if obj.get("/Subtype") == "/Image":
            if key not in found:
                semantic = json.dumps(_semantic(obj), sort_keys=True).encode()
                found[key] = {
                    "objectId": f"{key[0]}:{key[1]}",
                    "width": int(obj["/Width"]),
                    "height": int(obj["/Height"]),
                    "encodedBytes": len(obj._data),
                    "semanticHash": sha256(semantic).hexdigest(),
                    "pages": [],
                }
            if page not in found[key]["pages"]:
                found[key]["pages"].append(page)
            for name in ("/SMask", "/Mask"):
                mask = obj.get(name)
                if isinstance(mask, IndirectObject) and isinstance(
                    mask.get_object(), StreamObject
                ):
                    visit(mask, page, active)
        resources = obj.get("/Resources")
        if resources is not None:
            resources = resources.get_object()
            xobjects = resources.get("/XObject")
            if xobjects is not None:
                for child in xobjects.get_object().values():
                    visit(child, page, active)

    for number, page in enumerate(reader.pages, 1):
        visit(page, number, set())
    return list(found.values())


def qualify_resources(
    pdf_bytes: bytes, evidence: dict, *, fixture=False, baseline_bytes=None
) -> dict:
    """Reject repeated/oversized assets using placement contracts, never a byte cap."""
    import math

    images = image_inventory(pdf_bytes)
    logos = [
        image for image in images if (image["width"], image["height"]) == (263, 263)
    ]
    if len(logos) != 1:
        raise ValueError("PDF must contain one shared 263-pixel logo")
    if any(image["width"] == 2048 and image["height"] == 2048 for image in images):
        raise ValueError("PDF contains an oversized master logo")
    if any(image["width"] == 922 and image["height"] in (1, 185) for image in images):
        raise ValueError("PDF contains timeline background rasters")
    render = evidence["render"]
    maps = render.get("maps", {})
    matched_maps = []
    for page in render.get("fit", {}).get("pages", []):
        placement = page.get("mapPlacement")
        if not placement:
            continue
        stage = maps[page["legId"]]
        box = placement["boundsPx"]
        expected = (
            math.ceil((box[2] - box[0]) * 300 / 96),
            math.ceil((box[3] - box[1]) * 300 / 96),
        )
        viewport = stage.get("viewport", {})
        if (viewport.get("width"), viewport.get("height")) != expected:
            raise ValueError("Map viewport differs from final printed placement")
        candidates = [
            image
            for image in images
            if page["page"] in image["pages"]
            and (image["width"], image["height"]) == expected
        ]
        if len(candidates) != 1:
            raise ValueError("PDF map image differs from final printed placement")
        matched_maps.append(candidates[0]["semanticHash"])
    page_count = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    if fixture and (
        page_count != 5 or len(matched_maps) != 3 or len(set(matched_maps)) != 3
    ):
        raise ValueError(
            "Resource fixture must have five pages and three distinct maps"
        )
    if baseline_bytes is not None and len(pdf_bytes) >= baseline_bytes:
        raise ValueError("Corrected fixture did not reduce baseline bytes")
    return {
        "pdfBytes": len(pdf_bytes),
        "pageCount": page_count,
        "images": images,
        "imageStreamBytes": sum(image["encodedBytes"] for image in images),
        "baselineBytes": baseline_bytes,
        "savedBytes": baseline_bytes - len(pdf_bytes) if baseline_bytes else None,
    }
