"""Keep all Poppler text/geometry while excluding identified generation clocks."""

import xml.etree.ElementTree as ET
from hashlib import sha256


def geometry_text_hash(text):
    root = ET.fromstring(text)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "meta" and element.attrib.get("name") in {
            "CreationDate",
            "ModDate",
        }:
            element.set("content", "identified-generation-clock")
    return sha256(ET.tostring(root, encoding="utf-8")).hexdigest()
