"""Independent PDF fragments with shared profiles and unequal image semantics."""

import io
import json
from dataclasses import replace
from hashlib import sha256

from PIL import ImageCms
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from tests.unit.test_customer_document import inputs


def make_pdf_fragments():
    captured = inputs()[0]
    ids = ("a", "b", "c")
    captured = replace(
        captured, legs=tuple(replace(captured.legs[0], leg_id=i) for i in ids)
    )
    records = {}
    profile_bytes = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    for n, leg in enumerate(ids):
        writer = PdfWriter()

        def stream(data, attrs, writer=writer):
            value = DecodedStreamObject()
            value.set_data(data)
            value.update({NameObject(k): v for k, v in attrs.items()})
            return writer._add_object(value)

        profile = stream(profile_bytes, {"/N": NumberObject(3)})
        space = ArrayObject([NameObject("/ICCBased"), profile])

        def image(data, color=space, mask=None):
            attrs = {
                "/Type": NameObject("/XObject"),
                "/Subtype": NameObject("/Image"),
                "/Width": NumberObject(4),
                "/Height": NumberObject(4),
                "/BitsPerComponent": NumberObject(8),
                "/ColorSpace": color,
            }
            if mask is not None:
                attrs["/SMask"] = mask
            return stream(data, attrs)

        pixels = bytes(range(48))
        logo = image(pixels)
        route = image(bytes([80 + n] * 48), NameObject("/DeviceRGB"))
        mask = image(bytes([80 + n] * 16), NameObject("/DeviceGray"))
        masked = image(pixels, mask=mask)
        # Same pixels, unequal color space and separate profile references.
        control = image(pixels, NameObject("/DeviceRGB"))
        form = stream(
            b"q 63 0 0 63 20 400 cm /Logo Do Q q 210 0 0 202.5 500 200 cm /Map Do Q "
            b"q 63 0 0 63 100 400 cm /Masked Do Q q 63 0 0 63 180 400 cm /Control Do Q",
            {
                "/Type": NameObject("/XObject"),
                "/Subtype": NameObject("/Form"),
                "/BBox": ArrayObject([NumberObject(v) for v in [0, 0, 960, 540]]),
                "/Resources": DictionaryObject(
                    {
                        NameObject("/XObject"): DictionaryObject(
                            {
                                NameObject("/Logo"): logo,
                                NameObject("/Map"): route,
                                NameObject("/Masked"): masked,
                                NameObject("/Control"): control,
                            }
                        )
                    }
                ),
            },
        )
        font = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        )
        pages = []
        for index in range((2, 1, 2)[n]):
            page = writer.add_blank_page(width=960, height=540)
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/XObject"): DictionaryObject(
                        {NameObject("/Nested"): form}
                    ),
                    NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
                }
            )
            label = f"{leg} page {index + 1}"
            page[NameObject("/Contents")] = stream(
                f"/Nested Do BT /F1 12 Tf 20 20 Td ({label}) Tj ET".encode(), {}
            )
            pages.append({"page": index + 1, "legId": leg, "rowIds": [label]})
        stream(b"orphan must disappear", {})
        output = io.BytesIO()
        writer.write(output)
        writer.close()
        pdf = output.getvalue()
        records[leg] = {
            "state": "ready",
            "fingerprint": leg,
            "pdf": pdf,
            "evidence": json.dumps(
                {
                    "legs": [{"legId": leg}],
                    "pages": pages,
                    "render": {
                        "fit": {"pages": pages},
                        "maps": {leg: {"status": "ready"}},
                        "pdfValidation": {"rows": pages},
                        "artifactHashes": {"pdfPath": sha256(pdf).hexdigest()},
                    },
                }
            ).encode(),
        }
    return captured, records
