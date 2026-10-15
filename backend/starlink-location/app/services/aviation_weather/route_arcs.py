"""Shortest spherical arcs and conservative, seam-split lon/lat enclosures."""

import math

RADIUS_M = 6_371_008.8
TERMINAL_M = 18.52
GUARD_DEGREES = 1e-9


def _vector(point):
    lon, lat = map(math.radians, point)
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


class GreatCircleArc:
    def __init__(self, start, end):
        self.start, self.end = list(start), list(end)
        self.u, v = _vector(start), _vector(end)
        cross = (
            self.u[1] * v[2] - self.u[2] * v[1],
            self.u[2] * v[0] - self.u[0] * v[2],
            self.u[0] * v[1] - self.u[1] * v[0],
        )
        dot = sum(x * y for x, y in zip(self.u, v))
        self.angle = math.atan2(math.hypot(*cross), dot)
        if math.pi - self.angle <= 1e-10:
            raise ValueError("ambiguous antipodal route arc")
        self.length_m = self.angle * RADIUS_M
        if self.angle <= 1e-15:
            self.w = (0.0, 0.0, 0.0)
            self.length_m = 0.0
        else:
            self.w = tuple(
                (y - x * math.cos(self.angle)) / math.sin(self.angle)
                for x, y in zip(self.u, v)
            )
        self.direction = self.u[0] * self.w[1] - self.u[1] * self.w[0]

    def point(self, fraction):
        if fraction == 0:
            return self.start.copy()
        if fraction == 1:
            return self.end.copy()
        s = fraction * self.angle
        x, y, z = (u * math.cos(s) + w * math.sin(s) for u, w in zip(self.u, self.w))
        return [
            math.degrees(math.atan2(y, x)),
            math.degrees(math.atan2(z, math.hypot(x, y))),
        ]

    def enclosures(self, left, right):
        """Return boxes enclosing the curve, including interior latitude extrema."""
        p, q = self.point(left), self.point(right)
        latitudes = [p[1], q[1]]
        root = math.atan2(self.w[2], self.u[2])
        for k in range(-2, 3):
            s = root + k * math.pi
            if left * self.angle <= s <= right * self.angle and self.angle:
                latitudes.append(self.point(s / self.angle)[1])
        bottom = max(-90.0, min(latitudes) - GUARD_DEGREES)
        top = min(90.0, max(latitudes) + GUARD_DEGREES)
        if bottom == -90 or top == 90:
            return [(-180.0, bottom, 180.0, top)]
        delta = q[0] - p[0]
        if self.direction > 0:
            delta %= 360
        elif self.direction < 0:
            delta = -((-delta) % 360)
        elif abs(delta) > 180:
            # Numerically indeterminate winding cannot prove an outside interval.
            return [(-180.0, bottom, 180.0, top)]
        lo, hi = sorted((p[0], p[0] + delta))
        lo -= GUARD_DEGREES
        hi += GUARD_DEGREES
        if hi - lo >= 360:
            return [(-180.0, bottom, 180.0, top)]
        while lo < -180:
            lo += 360
            hi += 360
        while lo >= 180:
            lo -= 360
            hi -= 360
        if hi > 180:
            return [(lo, bottom, 180.0, top), (-180.0, bottom, hi - 360, top)]
        return [(lo, bottom, hi, top)]
