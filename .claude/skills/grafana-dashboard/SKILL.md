---
name: grafana-dashboard
description: Create and edit Grafana dashboards in JSON format. Use when working with Grafana dashboard files, adding panels, configuring visualizations, setting up queries, creating new dashboards, modifying existing dashboards, adding Prometheus queries, configuring geomap panels, setting up time series visualizations, dashboard layout, panel types, datasources, or any Grafana dashboard configuration tasks.
---

# Grafana Dashboard Development

## Purpose

Provides comprehensive guidance for creating and editing Grafana dashboards in JSON format, including panel configuration, Prometheus queries, visualizations, and layout management.

## When to Use This Skill

Automatically activates when working with:
- Creating new Grafana dashboards
- Editing existing dashboard JSON files
- Adding or modifying panels
- Configuring Prometheus queries
- Setting up visualizations (time series, geomap, stat, gauge, etc.)
- Dashboard layout and grid positioning
- Panel types and configuration options

---

## Project Context

### Dashboard Location

**Path:** `monitoring/grafana/provisioning/dashboards/`

**Existing Dashboards:**
- `fullscreen-overview.json` - Fullscreen kiosk mode overview with map
- `overview.json` - Main overview dashboard
- `network-metrics.json` - Network performance metrics
- `position-movement.json` - Position and movement tracking

**Provisioning Config:** `dashboards.yml` (auto-discovers JSON files)

### Available Prometheus Metrics

**Position:**
- `starlink_dish_latitude_degrees`
- `starlink_dish_longitude_degrees`
- `starlink_dish_altitude_meters`

**Network:**
- `starlink_network_latency_ms`
- `starlink_network_throughput_down_mbps`
- `starlink_network_throughput_up_mbps`

**Status:**
- `starlink_dish_obstruction_percent`
- `starlink_dish_speed_knots`
- `starlink_dish_heading_degrees`

**POI/ETA:**
- `starlink_eta_poi_seconds{name="..."}`
- `starlink_distance_to_poi_meters{name="..."}`

See `CLAUDE.md` for complete metrics list.

---

## Dashboard Structure

### Basic Dashboard Template

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "liveNow": true,
  "panels": [],
  "refresh": "1s",
  "schemaVersion": 39,
  "tags": ["starlink"],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-5m",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "browser",
  "title": "Dashboard Title",
  "uid": "unique-identifier",
  "version": 1
}
```

### Key Dashboard Properties

**`id`**: Always `null` for provisioned dashboards (auto-assigned by Grafana)

**`uid`**: Unique identifier (kebab-case, e.g., `starlink-overview`)

**`liveNow`**: Set to `true` for real-time data streaming

**`refresh`**: Auto-refresh interval (`"1s"`, `"5s"`, `"10s"`, etc.)

**`graphTooltip`**: Tooltip behavior
- `0` = Default (per panel)
- `1` = Shared crosshair
- `2` = Shared tooltip

---

## Panel Configuration

### Panel Grid Layout

Grafana uses a 24-column grid system:

```json
"gridPos": {
  "h": 8,    // Height (grid units)
  "w": 12,   // Width (1-24 columns)
  "x": 0,    // X position (0-23)
  "y": 0     // Y position (auto-stacks)
}
```

**Common Layouts:**
- Full width: `"w": 24`
- Half width: `"w": 12`
- Third width: `"w": 8`
- Quarter width: `"w": 6`

**Height Guidelines:**
- Small stat/gauge: `"h": 3-4`
- Medium time series: `"h": 8-10`
- Large map/graph: `"h": 12-16`

### Common Panel Types

See `PANEL_TYPES.md` for detailed panel configurations.

**Quick Reference:**
- `timeseries` - Line/area charts for time-based data
- `stat` - Single value with sparkline
- `gauge` - Progress/percentage indicator
- `geomap` - Maps with markers and routes
- `table` - Tabular data display
- `text` - Markdown/HTML content

---

## Prometheus Queries

### Basic Query Structure

```json
"targets": [
  {
    "datasource": {
      "type": "prometheus",
      "uid": "prometheus"
    },
    "expr": "starlink_network_latency_ms",
    "refId": "A",
    "instant": false,
    "range": true
  }
]
```

### Query Properties

**`expr`**: PromQL expression (metric name and operations)

**`refId`**: Query identifier (`"A"`, `"B"`, `"C"`, etc.)

**`instant`**: Get single latest value (`true`) or time range (`false`)

**`range`**: Include time range data (opposite of instant)

**`legendFormat`**: Custom legend text (e.g., `"{{name}}"`)

### Common PromQL Patterns

**Latest value:**
```promql
starlink_dish_latitude_degrees
```

**Average over time:**
```promql
avg_over_time(starlink_network_latency_ms[5m])
```

**Rate of change:**
```promql
rate(starlink_network_throughput_down_mbps[1m])
```

**Label filtering:**
```promql
starlink_eta_poi_seconds{name="destination"}
```

**Multiple metrics:**
```json
"targets": [
  {"expr": "starlink_network_latency_ms", "refId": "A"},
  {"expr": "starlink_network_throughput_down_mbps", "refId": "B"}
]
```

See `PROMETHEUS_QUERIES.md` for advanced query examples.

---

## Panel Examples

### Time Series Panel

```json
{
  "type": "timeseries",
  "title": "Network Latency",
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
  "id": 1,
  "targets": [{
    "datasource": {"type": "prometheus", "uid": "prometheus"},
    "expr": "starlink_network_latency_ms",
    "refId": "A"
  }],
  "fieldConfig": {
    "defaults": {
      "color": {"mode": "palette-classic"},
      "custom": {
        "axisLabel": "Latency (ms)",
        "drawStyle": "line",
        "lineInterpolation": "smooth",
        "fillOpacity": 20
      },
      "unit": "ms"
    }
  },
  "options": {
    "legend": {"calcs": ["last", "mean"], "displayMode": "table"}
  }
}
```

### Stat Panel (Single Value)

```json
{
  "type": "stat",
  "title": "Current Speed",
  "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
  "id": 2,
  "targets": [{
    "datasource": {"type": "prometheus", "uid": "prometheus"},
    "expr": "starlink_dish_speed_knots",
    "refId": "A"
  }],
  "fieldConfig": {
    "defaults": {
      "unit": "knots",
      "color": {"mode": "thresholds"},
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "red", "value": null},
          {"color": "yellow", "value": 5},
          {"color": "green", "value": 10}
        ]
      }
    }
  },
  "options": {
    "graphMode": "area",
    "colorMode": "background"
  }
}
```

### Geomap Panel

```json
{
  "type": "geomap",
  "title": "Position Map",
  "gridPos": {"h": 12, "w": 24, "x": 0, "y": 0},
  "id": 3,
  "targets": [
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "expr": "starlink_dish_latitude_degrees",
      "refId": "A"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "expr": "starlink_dish_longitude_degrees",
      "refId": "B"
    }
  ],
  "transformations": [
    {
      "id": "joinByField",
      "options": {
        "byField": "Time",
        "mode": "outer"
      }
    }
  ],
  "fieldConfig": {
    "defaults": {
      "custom": {
        "hideFrom": {"tooltip": false, "viz": false, "legend": false}
      }
    },
    "overrides": [
      {
        "matcher": {"id": "byName", "options": "starlink_dish_latitude_degrees"},
        "properties": [{"id": "displayName", "value": "latitude"}]
      },
      {
        "matcher": {"id": "byName", "options": "starlink_dish_longitude_degrees"},
        "properties": [{"id": "displayName", "value": "longitude"}]
      }
    ]
  },
  "options": {
    "view": {"id": "coords", "lat": 0, "lon": 0, "zoom": 2},
    "controls": {"showZoom": true, "showAttribution": true},
    "basemap": {
      "type": "default",
      "name": "Layer 0",
      "config": {}
    },
    "layers": [
      {
        "type": "markers",
        "name": "Current Position",
        "config": {
          "size": {"fixed": 8, "min": 2, "max": 15},
          "color": {"fixed": "dark-green"},
          "fillOpacity": 0.8,
          "shape": "circle"
        },
        "location": {"mode": "coords", "latitude": "latitude", "longitude": "longitude"}
      }
    ]
  }
}
```

---

## Best Practices

### Dashboard Design

1. **Panel Organization**
   - Group related metrics together
   - Use consistent sizing and alignment
   - Place most important panels at the top
   - Use full-width panels for maps and complex visualizations

2. **Color Coding**
   - Use thresholds for status indicators (red/yellow/green)
   - Consistent color palette across dashboards
   - High contrast for readability

3. **Performance**
   - Limit panels per dashboard (< 20 for good performance)
   - Use appropriate time ranges (avoid large queries)
   - Set reasonable refresh intervals (1s for real-time, 5s+ otherwise)

4. **Readability**
   - Clear, descriptive panel titles
   - Include units in axis labels
   - Use legends with calc values (last, mean, max, min)
   - Add descriptions for complex panels

### Development Workflow

1. **Start from Existing Dashboard**
   - Copy similar panel from existing dashboard
   - Modify query and visualization settings
   - Adjust layout as needed

2. **Test in Grafana UI**
   - Edit dashboard in Grafana web interface
   - Test queries and visualizations
   - Export JSON when satisfied

3. **Manual JSON Editing**
   - Edit JSON directly for bulk changes
   - Use proper JSON syntax (trailing commas not allowed)
   - Validate JSON before saving

4. **Version Control**
   - Always commit dashboard changes
   - Include descriptive commit messages
   - Test after deploying changes

### Common Mistakes

**Trailing commas in JSON:**
```json
// ❌ WRONG (JSON doesn't allow trailing commas)
"panels": [
  {"id": 1},
  {"id": 2},  // ← Remove this comma
]

// ✅ CORRECT
"panels": [
  {"id": 1},
  {"id": 2}
]
```

**Wrong datasource UID:**
```json
// ❌ WRONG
"datasource": {"type": "prometheus", "uid": "wrong-name"}

// ✅ CORRECT
"datasource": {"type": "prometheus", "uid": "prometheus"}
```

**Overlapping grid positions:**
- Ensure panels don't overlap on the 24-column grid
- Check x + w ≤ 24 for all panels in same row

**Missing refId:**
```json
// ❌ WRONG
"targets": [{"expr": "metric"}]

// ✅ CORRECT
"targets": [{"expr": "metric", "refId": "A"}]
```

---

## Testing Changes

### Local Testing

1. **Restart Grafana:**
```bash
docker compose restart grafana
```

2. **Check Grafana Logs:**
```bash
docker compose logs -f grafana
```

3. **Access Dashboard:**
- Open http://localhost:3000
- Navigate to dashboards
- Verify new/modified dashboard appears

### Validation

**JSON Syntax:**
```bash
jq . monitoring/grafana/provisioning/dashboards/your-dashboard.json
```

**Dashboard Import:**
- Try importing JSON through Grafana UI
- Checks for syntax errors and invalid configurations

---

## Reference Files

For detailed information on specific topics:

### [PANEL_TYPES.md](PANEL_TYPES.md)
Complete panel type reference:
- Time series configuration options
- Stat panel customization
- Gauge panel settings
- Geomap advanced features
- Table formatting
- All available panel types with examples

### [PROMETHEUS_QUERIES.md](PROMETHEUS_QUERIES.md)
Advanced PromQL examples:
- Complex aggregations
- Multi-metric queries
- Label filtering and grouping
- Time-based calculations
- Transformations and formatting

---

## Quick Reference

### Create New Dashboard

1. Copy existing dashboard JSON as template
2. Change `uid` and `title`
3. Modify panels as needed
4. Validate JSON syntax
5. Restart Grafana to load dashboard

### Add Panel to Existing Dashboard

1. Find next available `id` number
2. Calculate `gridPos` for placement
3. Configure panel type and options
4. Add Prometheus queries
5. Validate and restart Grafana

### Modify Existing Panel

1. Read dashboard JSON file
2. Locate panel by `id` or `title`
3. Edit configuration as needed
4. Maintain JSON syntax (no trailing commas)
5. Validate and restart Grafana

---

**Skill Status**: COMPLETE
**Line Count**: < 500 lines (following 500-line rule)
**Progressive Disclosure**: Reference files for detailed panel types and queries
