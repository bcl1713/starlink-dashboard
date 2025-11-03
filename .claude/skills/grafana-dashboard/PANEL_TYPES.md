# Grafana Panel Types Reference

Complete reference for all Grafana panel types used in the Starlink dashboard project.

## Table of Contents

- [Time Series](#time-series)
- [Stat (Single Value)](#stat-single-value)
- [Gauge](#gauge)
- [Geomap](#geomap)
- [Table](#table)
- [Text](#text)
- [Clock Panel](#clock-panel)

---

## Time Series

Line/area charts for visualizing metrics over time.

### Basic Configuration

```json
{
  "type": "timeseries",
  "title": "Panel Title",
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
  "id": 1,
  "targets": [{
    "datasource": {"type": "prometheus", "uid": "prometheus"},
    "expr": "metric_name",
    "refId": "A"
  }],
  "fieldConfig": {
    "defaults": {
      "color": {"mode": "palette-classic"},
      "custom": {
        "axisLabel": "",
        "drawStyle": "line",
        "lineInterpolation": "linear",
        "fillOpacity": 0
      },
      "unit": "short"
    }
  }
}
```

### Draw Styles

**`drawStyle`** options:
- `"line"` - Standard line chart (default)
- `"bars"` - Bar chart
- `"points"` - Points only (no lines)

**`lineInterpolation`** options:
- `"linear"` - Straight lines between points
- `"smooth"` - Curved lines (bezier)
- `"stepBefore"` - Step function (before)
- `"stepAfter"` - Step function (after)

### Fill Options

**`fillOpacity`**: 0-100 (0 = no fill, 100 = solid)

**`fillGradient`**: Gradient mode
- `0` - No gradient
- `1-10` - Gradient strength

### Axis Configuration

```json
"custom": {
  "axisLabel": "Latency (ms)",
  "axisPlacement": "auto",
  "axisColorMode": "text",
  "axisBorderShow": true,
  "scaleDistribution": {
    "type": "linear"  // or "log"
  }
}
```

### Legend Configuration

```json
"options": {
  "legend": {
    "calcs": ["last", "mean", "max"],
    "displayMode": "table",  // or "list", "hidden"
    "placement": "bottom",   // or "right"
    "showLegend": true
  }
}
```

### Color Modes

```json
"color": {
  "mode": "palette-classic"  // Default color palette
}
// Other modes: "thresholds", "fixed", "shades"
```

---

## Stat (Single Value)

Display a single metric value with optional sparkline.

### Basic Configuration

```json
{
  "type": "stat",
  "title": "Current Value",
  "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
  "id": 2,
  "targets": [{
    "datasource": {"type": "prometheus", "uid": "prometheus"},
    "expr": "metric_name",
    "refId": "A"
  }],
  "fieldConfig": {
    "defaults": {
      "unit": "short",
      "color": {"mode": "thresholds"}
    }
  },
  "options": {
    "graphMode": "none",
    "colorMode": "value"
  }
}
```

### Graph Modes

**`graphMode`** options:
- `"none"` - No graph, value only
- `"area"` - Area sparkline behind value
- `"line"` - Line sparkline behind value

### Color Modes

**`colorMode`** options:
- `"value"` - Color the value text
- `"background"` - Color the background
- `"none"` - No color

### Text Modes

**`textMode`** options:
- `"auto"` - Automatic (shows value)
- `"value"` - Show only value
- `"value_and_name"` - Show value and field name
- `"name"` - Show only field name
- `"none"` - Hide text

### Orientation

```json
"options": {
  "orientation": "auto"  // or "horizontal", "vertical"
}
```

### Thresholds

```json
"fieldConfig": {
  "defaults": {
    "thresholds": {
      "mode": "absolute",
      "steps": [
        {"color": "red", "value": null},      // Default
        {"color": "yellow", "value": 50},
        {"color": "green", "value": 80}
      ]
    }
  }
}
```

---

## Gauge

Circular or horizontal gauge for percentage/progress indicators.

### Basic Configuration

```json
{
  "type": "gauge",
  "title": "Progress",
  "gridPos": {"h": 6, "w": 6, "x": 0, "y": 0},
  "id": 3,
  "targets": [{
    "datasource": {"type": "prometheus", "uid": "prometheus"},
    "expr": "metric_name",
    "refId": "A"
  }],
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "min": 0,
      "max": 100,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 60},
          {"color": "red", "value": 80}
        ]
      }
    }
  },
  "options": {
    "showThresholdLabels": true,
    "showThresholdMarkers": true
  }
}
```

### Orientation

```json
"options": {
  "orientation": "auto"  // or "horizontal", "vertical"
}
```

### Display Options

```json
"options": {
  "showThresholdLabels": true,   // Show min/max labels
  "showThresholdMarkers": true,  // Show threshold lines
  "text": {
    "titleSize": 12,
    "valueSize": 24
  }
}
```

---

## Geomap

Map visualization with markers, routes, and heatmaps.

### Basic Configuration

```json
{
  "type": "geomap",
  "title": "Position Map",
  "gridPos": {"h": 12, "w": 24, "x": 0, "y": 0},
  "id": 4,
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
  "options": {
    "view": {
      "id": "coords",
      "lat": 0,
      "lon": 0,
      "zoom": 2
    },
    "controls": {
      "showZoom": true,
      "showAttribution": true
    }
  }
}
```

### Coordinate Transformation

Required when using separate lat/lon queries:

```json
"transformations": [
  {
    "id": "joinByField",
    "options": {
      "byField": "Time",
      "mode": "outer"
    }
  }
]
```

### Field Overrides

Rename fields for geomap layer configuration:

```json
"fieldConfig": {
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
}
```

### Marker Layer

```json
"layers": [
  {
    "type": "markers",
    "name": "Current Position",
    "config": {
      "size": {
        "fixed": 8,
        "min": 2,
        "max": 15
      },
      "color": {
        "fixed": "dark-green"
      },
      "fillOpacity": 0.8,
      "shape": "circle"
    },
    "location": {
      "mode": "coords",
      "latitude": "latitude",
      "longitude": "longitude"
    }
  }
]
```

**Available shapes:**
- `"circle"` - Circle marker
- `"square"` - Square marker
- `"triangle"` - Triangle marker
- `"star"` - Star marker

### Route Layer

```json
"layers": [
  {
    "type": "route",
    "name": "Historical Route",
    "config": {
      "style": {
        "color": {
          "fixed": "blue"
        },
        "opacity": 0.8,
        "lineWidth": 2
      }
    },
    "location": {
      "mode": "coords",
      "latitude": "latitude",
      "longitude": "longitude"
    }
  }
]
```

### Basemap Options

```json
"basemap": {
  "type": "default",     // OpenStreetMap
  "name": "Layer 0",
  "config": {}
}
// Other types: "esri-streets", "esri-topo", "esri-satellite"
```

### View Controls

```json
"view": {
  "id": "coords",
  "lat": 38.9,           // Initial center latitude
  "lon": -77.0,          // Initial center longitude
  "zoom": 10,            // Zoom level (1-20)
  "shared": true,        // Share view across dashboards
  "allLayers": true      // Show all layers
}
```

---

## Table

Tabular data display with sorting and filtering.

### Basic Configuration

```json
{
  "type": "table",
  "title": "Data Table",
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
  "id": 5,
  "targets": [{
    "datasource": {"type": "prometheus", "uid": "prometheus"},
    "expr": "metric_name",
    "refId": "A",
    "format": "table"
  }],
  "options": {
    "showHeader": true,
    "sortBy": []
  }
}
```

### Column Overrides

```json
"fieldConfig": {
  "overrides": [
    {
      "matcher": {"id": "byName", "options": "Value"},
      "properties": [
        {"id": "unit", "value": "ms"},
        {"id": "decimals", "value": 2},
        {"id": "custom.width", "value": 100}
      ]
    }
  ]
}
```

### Cell Display Mode

```json
"fieldConfig": {
  "defaults": {
    "custom": {
      "displayMode": "auto"  // or "color-background", "color-text", "gradient-gauge"
    }
  }
}
```

---

## Text

Static or dynamic text content (Markdown/HTML).

### Basic Configuration

```json
{
  "type": "text",
  "title": "Information",
  "gridPos": {"h": 4, "w": 12, "x": 0, "y": 0},
  "id": 6,
  "options": {
    "mode": "markdown",
    "content": "# Heading\n\nMarkdown content here"
  }
}
```

### Content Modes

**`mode`** options:
- `"markdown"` - Markdown formatting
- `"html"` - HTML formatting
- `"code"` - Code block (syntax highlighting)

---

## Clock Panel

Display time in various timezones.

**Note:** Requires grafana-clock-panel plugin (pre-installed in Grafana).

### Basic Configuration

```json
{
  "type": "grafana-clock-panel",
  "title": "UTC (Zulu)",
  "gridPos": {"h": 3, "w": 6, "x": 0, "y": 0},
  "id": 7,
  "options": {
    "timezone": "UTC",
    "clockType": "24 hour",
    "showDate": false,
    "showSeconds": true,
    "timeSettings": {
      "fontSize": "24px",
      "fontWeight": "bold"
    },
    "timezoneSettings": {
      "fontSize": "12px",
      "fontWeight": "normal",
      "showTimezone": true,
      "zoneFormat": "offset"
    }
  }
}
```

### Clock Types

**`clockType`** options:
- `"24 hour"` - 24-hour format
- `"12 hour"` - 12-hour format with AM/PM

### Common Timezones

- `"UTC"` - Coordinated Universal Time (Zulu)
- `"America/New_York"` - Eastern Time
- `"America/Chicago"` - Central Time
- `"America/Denver"` - Mountain Time
- `"America/Los_Angeles"` - Pacific Time
- `"Europe/London"` - GMT/BST
- `"browser"` - Use browser timezone

---

## Common Field Config Options

These options apply to most panel types.

### Units

Common unit options:
- `"short"` - Default (no unit)
- `"percent"` - Percentage (0-100)
- `"ms"` - Milliseconds
- `"s"` - Seconds
- `"bytes"` - Bytes (auto-scaling)
- `"bps"` - Bits per second
- `"Bps"` - Bytes per second
- `"meters"` - Meters
- `"degrees"` - Degrees
- `"knots"` - Knots (nautical miles per hour)

### Decimals

```json
"decimals": 2  // Number of decimal places (0-10)
```

### Min/Max Values

```json
"min": 0,
"max": 100
```

### Custom Display Name

```json
"displayName": "Custom Name"
```

---

## Tips and Best Practices

1. **Panel IDs**: Use sequential IDs (1, 2, 3...) for clarity
2. **Grid Layout**: Keep x + w ≤ 24 to avoid overlaps
3. **Consistent Heights**: Use standard heights (3, 4, 8, 12) for alignment
4. **Color Coding**: Use thresholds consistently across similar panels
5. **Performance**: Limit panels per dashboard (< 20 recommended)
6. **Units**: Always specify appropriate units for readability
7. **Legends**: Include calc values (last, mean, max) for context
8. **Testing**: Test panels in Grafana UI before committing JSON
