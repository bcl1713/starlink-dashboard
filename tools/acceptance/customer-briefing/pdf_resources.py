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
            result = {str(k): _semantic(v, active) for k, v in sorted(value.items())
                      if str(k) not in {"/Length", "/Filter", "/DecodeParms"}}
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
        key = (ref.idnum, ref.generation) if isinstance(ref, IndirectObject) else (id(obj), 0)
        if key in active:
            return
        active = active | {key}
        if obj.get("/Subtype") == "/Image":
            if key not in found:
                semantic = json.dumps(_semantic(obj), sort_keys=True).encode()
                found[key] = {
                    "objectId": f"{key[0]}:{key[1]}", "width": int(obj["/Width"]),
                    "height": int(obj["/Height"]), "encodedBytes": len(obj._data),
                    "semanticHash": sha256(semantic).hexdigest(), "pages": [],
                }
            if page not in found[key]["pages"]:
                found[key]["pages"].append(page)
            for name in ("/SMask", "/Mask"):
                mask = obj.get(name)
                if isinstance(mask, IndirectObject) and isinstance(mask.get_object(), StreamObject):
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
