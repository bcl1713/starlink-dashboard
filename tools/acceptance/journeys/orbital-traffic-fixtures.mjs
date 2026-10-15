import { readFile } from "node:fs/promises";
export async function makeCatalog(size, utcMs = Date.now(), expired = false) {
  const fixture = JSON.parse(
    await readFile(
      new URL("./orbital-traffic-fixtures/omm-template.json", import.meta.url),
      "utf8",
    ),
  );
  const objects = Array.from({ length: size }, (_, i) => ({
    ...fixture.object,
    NORAD_CAT_ID: String(100000000 + i),
    EPOCH: new Date(utcMs - (expired ? 73 * 3600000 : 0)).toISOString(),
    RA_OF_ASC_NODE: ((i % 64) * 360) / 64,
    MEAN_ANOMALY: (Math.floor(i / 64) * 360) / Math.ceil(size / 64),
  }));
  return {
    generation: `synthetic-${size}-${utcMs}-${expired}`,
    acquired_at: new Date(utcMs).toISOString(),
    last_attempt_at: new Date(utcMs).toISOString(),
    retry_after_at: null,
    suspended: false,
    objects,
    rejected_count: 0,
    truncated_count: 0,
    eligible_count: size,
    status: size ? "ready" : "loading",
  };
}
export function statusFixture({
  warning = false,
  invalid = false,
  stale = false,
  unavailable = false,
  zero = false,
  disconnected = false,
} = {}) {
  return {
    timestamp: new Date(Date.now() - (stale ? 60000 : 0)).toISOString(),
    position: {
      latitude: invalid ? null : 0,
      longitude: 0,
      altitude: 35000,
      speed: 450,
      heading: 90,
    },
    ground_entry_point: { latitude: 0, longitude: disconnected ? 120 : 0 },
    network: {
      throughput_up_mbps: zero ? 0 : 80,
      throughput_down_mbps: zero ? 0 : 25,
      latency_ms: 20,
      packet_loss_percent: 0,
    },
    metric_availability: {
      throughput_up_mbps: !unavailable,
      throughput_down_mbps: !unavailable,
      latency_ms: true,
      packet_loss_percent: true,
    },
    warning,
  };
}
export async function installFixtureRoutes(page, state) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const json = async (data) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data),
      });
    if (path === "/api/status")
      return state.statusFailure
        ? route.fulfill({ status: 503, body: "controlled unavailable" })
        : json(statusFixture(state));
    if (path === "/api/routes")
      return json({
        routes: [
          { id: "fixture", name: "Orbital acceptance route", is_active: true },
        ],
        total: 1,
      });
    if (path === "/api/routes/fixture")
      return json({
        id: "fixture",
        points: [
          { latitude: 0, longitude: -10 },
          { latitude: 0, longitude: 0 },
          { latitude: 5, longitude: 10 },
        ],
      });
    if (path === "/api/satellites")
      return json([
        {
          satellite_id: "X-6",
          transport: "X",
          longitude: 0,
          slot: null,
          color: "#ff6b6b",
        },
      ]);
    if (path === "/api/active-x-link")
      return json({
        satellite_id: "X-6",
        state: state.warning ? "warning" : "normal",
      });
    if (path === "/api/overview-history") {
      const now = Date.now() / 1000;
      return json({
        window_seconds: 300,
        start_timestamp_seconds: now - 300,
        end_timestamp_seconds: now,
        step_seconds: 5,
        series: {
          starlink_dish_latitude_degrees: [
            [now - 30, 0],
            [now, 0],
          ],
          starlink_dish_longitude_degrees: [
            [now - 30, -1],
            [now, 0],
          ],
          altitude: [
            [now - 30, 35000],
            [now, 35000],
          ],
        },
      });
    }
    if (path === "/api/overview/upcoming-pois")
      return json({ state: "no_generated_pois", pois: [] });
    if (path.startsWith("/api/orbital/viewers/")) {
      if (route.request().method() === "DELETE") {
        state.leases.delete(path);
        return route.fulfill({ status: 204 });
      }
      state.leases.add(path);
      return json({ expires_at: new Date(Date.now() + 75000).toISOString() });
    }
    if (path === "/api/orbital/catalog") {
      state.catalogRequests++;
      if (state.catalogDelay) await state.catalogDelay;
      return json(state.catalog);
    }
    if (path === "/api/orbital/status") {
      const { objects, ...diagnostics } = state.catalog;
      void objects;
      return json({ ...diagnostics, active_viewers: state.leases.size });
    }
    return route.continue();
  });
}
