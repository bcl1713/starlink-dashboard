"""Compatibility projection of the existing leased radar manifest."""

import hashlib
import json

from app.models.aviation_weather import Coverage, WeatherProduct
from app.models.overview_weather import WeatherManifest


def identity(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def radar_product(manifest: WeatherManifest | None, now_ms: int):
    base = {
        "layer_id": "observed-radar",
        "product_type": "observed-precipitation",
        "representation": "xyz-rgba-pair-v1",
        "source_id": manifest.source if manifest else "radar",
        "provenance": manifest.provenance if manifest else "Observed radar unavailable",
        "attribution": (
            [manifest.attribution]
            if manifest
            else [{"label": "Radar", "url": "https://www.rainviewer.com/"}]
        ),
        "time_kind": "observation",
        "method_kind": "sensor",
        "validity_kind": "instant",
        "vertical": {"kind": "not-applicable"},
        "generated_at_ms": now_ms,
        "product_id": (
            manifest.product_id
            if manifest
            else identity({"representation": "xyz-rgba-pair-v1"})
        ),
    }
    if manifest is None or manifest.state != "ready":
        return WeatherProduct(
            state=manifest.state if manifest else "unavailable", **base
        )
    frame = manifest.frame_time_ms
    expiry = min(frame + 3600000, manifest.coverage_expires_at_ms)
    if frame > now_ms + 60000 or now_ms >= expiry:
        return WeatherProduct(state="unavailable", **base)
    return WeatherProduct(
        **base,
        state="stale" if now_ms >= frame + 1200000 else "ready",
        observed_at_ms=frame,
        valid_at_ms=frame,
        retrieved_at_ms=min(manifest.generated_at_ms, now_ms),
        fresh_until_ms=min(frame + 1200000, expiry),
        expires_at_ms=expiry,
        instance_id=identity(
            {
                "product_id": manifest.product_id,
                "frame": frame,
                "coverage": manifest.coverage_token,
                "coverage_expiry": manifest.coverage_expires_at_ms,
            }
        ),
        coverage=Coverage(
            generation=str(manifest.coverage_token),
            expires_at_ms=manifest.coverage_expires_at_ms,
            mask_encoding="absence-rgba-v1",
            missing_meaning="unknown-not-clear",
            feed_completeness="unknown",
        ),
        radar=manifest,
    )
