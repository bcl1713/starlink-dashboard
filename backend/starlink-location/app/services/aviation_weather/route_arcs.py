"""Shortest spherical arcs and conservative, seam-split lon/lat enclosures."""

import math

RADIUS_M = 6_371_008.8
TERMINAL_M = 18.52
GUARD_DEGREES = 1e-9


def _vector(point):
    lon, lat = map(math.radians, point)
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def _cross(u, v):
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _unit(vector):
    length = math.hypot(*vector)
    return tuple(value / length for value in vector)


class GreatCircleArc:
    def __init__(self, start, end):
        self.start, self.end = list(start), list(end)
        self.u, v = _unit(_vector(start)), _unit(_vector(end))
        cross = _cross(self.u, v)
        cross_length = math.hypot(*cross)
        dot = sum(x * y for x, y in zip(self.u, v))
        self.angle = math.atan2(cross_length, dot)
        if math.pi - self.angle <= 1e-10:
            raise ValueError("ambiguous antipodal route arc")
        self.length_m = self.angle * RADIUS_M
        # Near antipodes, forming the great-circle plane amplifies endpoint
        # roundoff by 1/|u x v|. Reserve a 32-ulp vector error allowance; if that
        # amplification exceeds the existing angular enclosure guard, do not
        # certify this arc. This is uncertainty, not an enlarged route corridor.
        # Restrict the gate to obtuse arcs: small-angle legs do not traverse the
        # unstable distant portion of their plane and must remain usable.
        self.numerically_uncertain = dot < 0 and cross_length < 32 * math.ulp(
            1.0
        ) / math.radians(GUARD_DEGREES)
        if self.angle <= 1e-15:
            self.w = (0.0, 0.0, 0.0)
            self.length_m = 0.0
        else:
            # Equivalent to (v-u*cos(a))/sin(a), avoiding that subtraction's
            # loss of orthogonality for both short and near-antipodal arcs.
            normal = _unit(cross)
            self.w = _unit(_cross(normal, self.u))
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
        if self.numerically_uncertain:
            return [(-180.0, -90.0, 180.0, 90.0)]
        p, q = self.point(left), self.point(right)
        latitudes = [p[1], q[1]]
        # Account for the remaining floating-point norm/dot residuals instead
        # of assuming a mathematically exact orthonormal basis at an extremum.
        uu = sum(value * value for value in self.u)
        ww = sum(value * value for value in self.w)
        uw = sum(u * w for u, w in zip(self.u, self.w))
        root = math.atan2(
            self.w[2] * uu - self.u[2] * uw,
            self.u[2] * ww - self.w[2] * uw,
        )
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
