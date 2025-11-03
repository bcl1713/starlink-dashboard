# Prometheus Queries Reference

Advanced PromQL examples for Grafana dashboards in the Starlink project.

## Table of Contents

- [Basic Queries](#basic-queries)
- [Time-Based Functions](#time-based-functions)
- [Aggregation](#aggregation)
- [Label Filtering](#label-filtering)
- [Mathematical Operations](#mathematical-operations)
- [Starlink-Specific Examples](#starlink-specific-examples)

---

## Basic Queries

### Instant Query

Get the most recent value:

```promql
starlink_dish_latitude_degrees
```

```json
{
  "expr": "starlink_dish_latitude_degrees",
  "refId": "A",
  "instant": true,
  "range": false
}
```

### Range Query

Get values over time range:

```promql
starlink_network_latency_ms
```

```json
{
  "expr": "starlink_network_latency_ms",
  "refId": "A",
  "instant": false,
  "range": true
}
```

---

## Time-Based Functions

### Rate

Calculate per-second rate of increase:

```promql
rate(starlink_network_throughput_down_mbps[1m])
```

**Use cases:**
- Network throughput changes
- Counter metrics
- Traffic analysis

### Increase

Total increase over time range:

```promql
increase(starlink_network_throughput_down_mbps[5m])
```

### Average Over Time

Average value over time window:

```promql
avg_over_time(starlink_network_latency_ms[5m])
```

**Other aggregation functions:**
- `min_over_time()` - Minimum value
- `max_over_time()` - Maximum value
- `sum_over_time()` - Sum of values
- `count_over_time()` - Count of values

### Delta

Difference between first and last value:

```promql
delta(starlink_dish_altitude_meters[1h])
```

**Use cases:**
- Altitude changes
- Position drift
- Cumulative changes

### Deriv

Per-second derivative (rate of change):

```promql
deriv(starlink_dish_altitude_meters[5m])
```

**Use cases:**
- Rate of climb/descent
- Acceleration
- Trend analysis

---

## Aggregation

### Average

Average across all series:

```promql
avg(starlink_network_latency_ms)
```

### Sum

Sum across all series:

```promql
sum(starlink_distance_to_poi_meters)
```

### Min/Max

Minimum or maximum value:

```promql
min(starlink_network_latency_ms)
max(starlink_network_latency_ms)
```

### Count

Number of series:

```promql
count(starlink_eta_poi_seconds)
```

### Group By Label

Aggregate by label:

```promql
avg by (name) (starlink_eta_poi_seconds)
```

**Result:** One series per unique `name` label value

---

## Label Filtering

### Exact Match

```promql
starlink_eta_poi_seconds{name="destination"}
```

### Regex Match

```promql
starlink_eta_poi_seconds{name=~"dest.*"}
```

### Not Equal

```promql
starlink_eta_poi_seconds{name!="waypoint"}
```

### Regex Not Match

```promql
starlink_eta_poi_seconds{name!~"temp.*"}
```

### Multiple Conditions

```promql
starlink_eta_poi_seconds{name="destination", type="airport"}
```

---

## Mathematical Operations

### Arithmetic

**Addition:**
```promql
starlink_network_throughput_down_mbps + starlink_network_throughput_up_mbps
```

**Subtraction:**
```promql
starlink_dish_altitude_meters - 100
```

**Multiplication:**
```promql
starlink_dish_speed_knots * 1.852  # Convert to km/h
```

**Division:**
```promql
starlink_distance_to_poi_meters / 1000  # Convert to kilometers
```

### Comparison Operators

**Greater than:**
```promql
starlink_network_latency_ms > 50
```

**Less than or equal:**
```promql
starlink_dish_obstruction_percent <= 5
```

**Equal:**
```promql
starlink_dish_speed_knots == 0
```

### Logical Operators

**AND:**
```promql
starlink_network_latency_ms > 50 and starlink_dish_obstruction_percent > 10
```

**OR:**
```promql
starlink_network_latency_ms > 100 or starlink_dish_obstruction_percent > 20
```

**UNLESS:**
```promql
starlink_network_latency_ms unless starlink_dish_obstruction_percent > 5
```

---

## Starlink-Specific Examples

### Network Performance

**Average latency over 5 minutes:**
```promql
avg_over_time(starlink_network_latency_ms[5m])
```

**Combined throughput (up + down):**
```promql
starlink_network_throughput_down_mbps + starlink_network_throughput_up_mbps
```

**Latency spike detection (> 100ms):**
```promql
starlink_network_latency_ms > 100
```

### Position and Movement

**Speed in kilometers per hour:**
```promql
starlink_dish_speed_knots * 1.852
```

**Rate of altitude change (vertical speed):**
```promql
deriv(starlink_dish_altitude_meters[1m]) * 60
```

**Distance traveled in last hour:**
```promql
increase(starlink_dish_speed_knots[1h]) * 1.852
```

### POI and ETA

**Time to closest POI:**
```promql
min(starlink_eta_poi_seconds)
```

**Distance to all POIs:**
```promql
starlink_distance_to_poi_meters
```

**POIs within 10km:**
```promql
starlink_distance_to_poi_meters < 10000
```

**ETA in minutes:**
```promql
starlink_eta_poi_seconds / 60
```

### Obstruction Analysis

**Average obstruction over time:**
```promql
avg_over_time(starlink_dish_obstruction_percent[10m])
```

**Time with obstructions (> 0%):**
```promql
count_over_time((starlink_dish_obstruction_percent > 0)[1h])
```

**Maximum obstruction in last hour:**
```promql
max_over_time(starlink_dish_obstruction_percent[1h])
```

---

## Multi-Metric Queries

### Multiple Queries in One Panel

```json
"targets": [
  {
    "expr": "starlink_network_latency_ms",
    "refId": "A",
    "legendFormat": "Latency"
  },
  {
    "expr": "starlink_dish_obstruction_percent * 10",
    "refId": "B",
    "legendFormat": "Obstruction (scaled)"
  }
]
```

### Calculated Metrics

**Query A:**
```promql
starlink_network_throughput_down_mbps
```

**Query B:**
```promql
starlink_network_throughput_up_mbps
```

**Query C (calculation in Grafana):**
```promql
$A + $B
```

---

## Legend Formatting

### Basic Legend

```json
{
  "expr": "starlink_network_latency_ms",
  "legendFormat": "Latency"
}
```

### Label in Legend

```json
{
  "expr": "starlink_eta_poi_seconds",
  "legendFormat": "ETA to {{name}}"
}
```

**Result:** "ETA to destination", "ETA to waypoint", etc.

### Multiple Labels

```json
{
  "expr": "starlink_distance_to_poi_meters",
  "legendFormat": "{{name}} ({{type}})"
}
```

---

## Query Options

### Step Size

Control query resolution:

```json
{
  "expr": "starlink_network_latency_ms",
  "interval": "",
  "intervalFactor": 1
}
```

**Auto step:** Leave `interval` empty for automatic calculation

**Fixed step:** Set `interval` to specific value (e.g., `"1s"`, `"5s"`)

### Format

Query result format:

```json
{
  "expr": "starlink_network_latency_ms",
  "format": "time_series"  // or "table", "heatmap"
}
```

---

## Best Practices

1. **Use Appropriate Time Windows**
   - Short windows (1m, 5m) for recent trends
   - Long windows (1h, 24h) for historical patterns
   - Match window size to data resolution

2. **Optimize Query Performance**
   - Use specific label filters to reduce data
   - Avoid unnecessary aggregations
   - Use recording rules for complex queries

3. **Legend Clarity**
   - Use descriptive legend formats
   - Include relevant labels in legend
   - Avoid overly long legends

4. **Rate vs. Increase**
   - Use `rate()` for per-second rates
   - Use `increase()` for total change
   - Always specify time window

5. **Aggregation Order**
   - Apply label filters first
   - Then apply time-based functions
   - Finally apply aggregations

6. **Testing Queries**
   - Test in Prometheus UI first
   - Verify results match expectations
   - Check query performance

---

## Common Patterns

### Moving Average

```promql
avg_over_time(starlink_network_latency_ms[5m])
```

### Percentage Change

```promql
(starlink_network_latency_ms - starlink_network_latency_ms offset 1h)
/ starlink_network_latency_ms offset 1h * 100
```

### Threshold Alert

```promql
starlink_network_latency_ms > 100
```

**Returns:** Only values exceeding threshold

### Uptime Percentage

```promql
avg_over_time(up[1h]) * 100
```

### Rate of Change

```promql
rate(starlink_network_throughput_down_mbps[1m])
```

---

## Troubleshooting

### No Data Returned

- Check metric name spelling
- Verify time range includes data
- Check label filters are correct
- Ensure datasource is configured

### Unexpected Results

- Verify time window size
- Check aggregation functions
- Test query in Prometheus UI
- Review label filtering

### Performance Issues

- Reduce time range
- Add label filters
- Simplify aggregations
- Use recording rules for complex queries

### Syntax Errors

- Check parentheses matching
- Verify function names
- Ensure label syntax is correct (`{label="value"}`)
- Use Prometheus query validator
