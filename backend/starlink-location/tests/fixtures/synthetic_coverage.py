"""Invented coverage boundaries shared by calculation and browser regressions."""


class SyntheticCoverage:
    """Fake POR/IOR boundaries; these are never operational polygons."""

    def check_coverage_at_point(self, latitude, longitude):
        satellites = []
        if longitude < -100 or longitude >= 172 or 120 <= longitude <= 166:
            satellites.append("POR")
        if 0 <= longitude <= 140:
            satellites.append("IOR")
        return satellites
