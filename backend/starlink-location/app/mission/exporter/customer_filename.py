"""Safe customer PDF names shared by package and evidence publication."""

import re


def customer_brief_filename(mission_name):
    """Keep the captured mission name while preventing paths and unsafe characters."""
    name = mission_name or "mission"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
    name = name.encode("utf-8")[:240].decode("utf-8", errors="ignore").rstrip(" ._")
    return f"{name or 'mission'}-brief.pdf"
