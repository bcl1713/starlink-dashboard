# Export data extraction

Capture the export snapshot before rendering and use the snapshot views rather
than refetching mutable mission, route or satellite inputs during generation.
This keeps maps, timelines and customer documents consistent. See
[export preparation](../planning/outputs.md) and
[`snapshot_views.py`](../../../backend/starlink-location/app/mission/exporter/snapshot_views.py).
