# API JavaScript Examples

[Back to API Reference](../README.md) | [Examples Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Fetch API (Browser)

```javascript
const BASE_URL = "http://localhost:8000";

// Get service health
async function checkHealth() {
  const response = await fetch(`${BASE_URL}/health`);
  const health = await response.json();
  console.log("Service status:", health.status);
  return health;
}

// Get current status
async function getCurrentStatus() {
  const response = await fetch(`${BASE_URL}/api/status`);
  const status = await response.json();
  console.log("Position:", status.position);
  console.log("Network:", status.network);
  return status;
}

// Create POI
async function createPOI(poiData) {
  const response = await fetch(`${BASE_URL}/api/pois`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(poiData),
  });
  const poi = await response.json();
  console.log("Created POI:", poi);
  return poi;
}

// Get ETAs
async function getETAs() {
  const response = await fetch(`${BASE_URL}/api/pois/etas`);
  const etas = await response.json();

  etas.forEach((poi) => {
    const etaMinutes = poi.eta_seconds / 60;
    const distanceKm = poi.distance_meters / 1000;
    console.log(
      `${poi.name}: ${etaMinutes.toFixed(1)} min (${distanceKm.toFixed(1)} km)`,
    );
  });

  return etas;
}

// Monitor route progress
async function monitorProgress(routeId) {
  setInterval(async () => {
    const response = await fetch(`${BASE_URL}/api/routes/${routeId}/progress`);
    const progress = await response.json();

    console.log(`Progress: ${progress.progress_percent.toFixed(1)}%`);
    console.log(
      `Waypoint: ${progress.current_waypoint_index}/${progress.total_waypoints}`,
    );
  }, 10000); // Update every 10 seconds
}
```

---

## Node.js with axios

```javascript
const axios = require("axios");

const BASE_URL = "http://localhost:8000";

// Get service health
async function checkHealth() {
  try {
    const response = await axios.get(`${BASE_URL}/health`);
    console.log("Service status:", response.data.status);
    return response.data;
  } catch (error) {
    console.error("Error:", error.message);
  }
}

// Create POI
async function createPOI(poiData) {
  try {
    const response = await axios.post(`${BASE_URL}/api/pois`, poiData);
    console.log("Created POI:", response.data);
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error("Error:", error.response.data);
    } else {
      console.error("Error:", error.message);
    }
  }
}

// Get ETAs
async function getETAs(params = {}) {
  try {
    const response = await axios.get(`${BASE_URL}/api/pois/etas`, { params });
    return response.data;
  } catch (error) {
    console.error("Error:", error.message);
  }
}

// Example usage
(async () => {
  await checkHealth();

  const poi = await createPOI({
    name: "Central Park",
    latitude: 40.7829,
    longitude: -73.9654,
    description: "NYC Central Park",
  });

  const etas = await getETAs();
  console.log("ETAs:", etas);
})();
```

---

[Back to API Reference](../README.md) | [Examples Index](./README.md)
