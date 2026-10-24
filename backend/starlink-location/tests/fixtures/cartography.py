"""Explicit, function-scoped offline cartography for real exporter renders."""

import cartopy
import pytest
from cartopy.feature import NaturalEarthFeature
from cartopy.io import Downloader
from shapely.geometry import LineString, box


@pytest.fixture
def offline_cartography(monkeypatch, tmp_path):
    """Use a private empty cache and reject external cartographic downloads."""
    cache = tmp_path / "cartopy"
    cache.mkdir()
    monkeypatch.setitem(cartopy.config, "data_dir", cache)
    monkeypatch.setitem(cartopy.config, "pre_existing_data_dir", cache)

    def deny_download(*args, **kwargs):
        raise AssertionError("External cartography download attempted")

    monkeypatch.setattr(Downloader, "_urlopen", deny_download)
    land = (box(-18, -35, 50, 65), box(65, 5, 140, 65), box(-130, 10, -60, 65))
    geometries = {
        ("physical", "coastline"): tuple(LineString(p.exterior.coords) for p in land),
        ("cultural", "admin_0_boundary_lines_land"): (
            LineString([(-10, 5), (15, 15), (40, 5)]),
            LineString([(70, 30), (100, 25), (135, 30)]),
        ),
        ("physical", "land"): land,
        ("physical", "ocean"): (box(-179, -80, 179, 80),),
    }
    requested = []

    def local_geometries(feature):
        key = (feature.category, feature.name)
        if key not in geometries or feature.scale not in {"10m", "50m", "110m"}:
            raise AssertionError(
                f"Unsupported Natural Earth dataset: {key} at {feature.scale}"
            )
        requested.append(key)
        return iter(geometries[key])

    monkeypatch.setattr(NaturalEarthFeature, "geometries", local_geometries)
    return {"cache": cache, "requested": requested}
