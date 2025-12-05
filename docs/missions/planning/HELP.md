# Troubleshooting & Support

## Troubleshooting

### Problem: "Route file is invalid"

**Causes:**

- File is not XML format (check extension is `.kml`)
- Missing `<LineString>` element (must have continuous path)
- Coordinates outside valid range (lat: -90 to +90, lon: -180 to +180)

**Solution:**

1. Open KML file in text editor
2. Search for `<LineString>` (must be present)
3. Check sample route: `simple-circular.kml` works 100% of the time
4. If repairing manually, validate at
   <<https://validator.kml4earth.appspot.com>>

---

### Problem: "Cannot add X transition at those coordinates"

**Cause:** Coordinates don't project to the route (distance > 100 km from
nearest waypoint).

**Solution:**

1. Verify coordinates are correct (use route map to click nearest waypoint)
2. Use waypoint coordinate, not estimated intersection
3. Check that route file includes your intended area

---

### Problem: "Timeline is all yellow/red"

**Cause:** Multiple overlapping constraints (e.g., Ka gap + X transition at same
time).

**Solution:**

1. Review timeline carefully—this is valid and important
2. If unexpected, check:
   - X transition timing (should be ±15 min only)
   - Ka coverage dates (coverage maps updated quarterly)
   - AAR window placement (may overlap with other degradation)
3. Contact mission planning if result seems wrong

---

### Problem: "Cannot export to PDF"

**Cause:** Browser JavaScript disabled or missing libraries.

**Solution:**

1. Enable JavaScript in browser settings
2. Try Chrome/Chromium instead (most reliable)
3. Export CSV and open in spreadsheet to create manual PDF

---

## FAQ

**Q: What if I have both X transition AND Ka gap at the same time?** A: Status
becomes CRITICAL (red). This is rare but possible. Use Ka as primary during X
transition, keeping Ku as fallback.

**Q: How accurate are coverage maps?** A: Ka and Ku coverage updated quarterly.
Predictions valid within ±5 minutes (weather/propagation effects not modeled).

**Q: Can I add multiple AAR windows?** A: Yes, click **Add AAR Window** multiple
times. Each blocks X-Band independently.

**Q: What timezone should I use in export?** A: Crew uses Eastern (local +
DST-aware). Controllers use UTC. System outputs both in exports.

**Q: How long does planning take?** A: 5-10 minutes per mission (routes,
transports, AAR windows). Timeline computation instant.

---

## Support

For questions or issues:

1. Check **Troubleshooting** section above
2. Review timeline chart (most questions answered by visual inspection)
3. Contact mission operations with mission name + timestamp

---

## Related Documents

- **[MISSION-COMM-SOP.md](../MISSION-COMM-SOP.md)** — Operations playbook for
  monitoring and alert response
- **[METRICS.md](../../METRICS.md)** — Prometheus metrics reference for
  dashboard integration
- **[API Reference](../../api/README.md)** — Mission planning API
  endpoints (for integrations)
