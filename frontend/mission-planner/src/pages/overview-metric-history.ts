import type {
  OverviewHistoryBundle,
  OverviewHistorySample,
} from '../services/overview-history';

export interface OverviewMetricGraphDescriptor {
  id: string;
  metric: string;
  label: string;
  unit: string;
}

export const OVERVIEW_METRIC_GRAPHS: readonly OverviewMetricGraphDescriptor[] =
  [
    {
      id: 'latency',
      metric: 'starlink_network_latency_ms_current',
      label: 'Network latency',
      unit: 'ms',
    },
    {
      id: 'downlink',
      metric: 'starlink_network_throughput_down_mbps_current',
      label: 'Downlink throughput',
      unit: 'Mbps',
    },
    {
      id: 'uplink',
      metric: 'starlink_network_throughput_up_mbps_current',
      label: 'Uplink throughput',
      unit: 'Mbps',
    },
    {
      id: 'packet-loss',
      metric: 'starlink_network_packet_loss_percent',
      label: 'Packet loss',
      unit: '%',
    },
    {
      id: 'obstruction',
      metric: 'starlink_dish_obstruction_percent',
      label: 'Dish obstruction',
      unit: '%',
    },
  ];

export interface ProjectedMetricTraces {
  state: 'available' | 'empty' | 'unavailable';
  times: number[];
  observed: (number | null)[];
  min: (number | null)[];
  avg: (number | null)[];
  max: (number | null)[];
}

export interface ProjectedMetricHistory extends ProjectedMetricTraces {
  visibleRightSeconds: number;
}

function validSamples(
  samples: OverviewHistorySample[] | undefined
): OverviewHistorySample[] {
  if (!Array.isArray(samples)) return [];
  return samples.filter(
    (sample) =>
      Array.isArray(sample) &&
      sample.length === 2 &&
      Number.isFinite(sample[0]) &&
      Number.isFinite(sample[1])
  );
}

/** Align four independent Prometheus traces without interpolating missing values. */
export function projectMetricTraces(
  bundle: OverviewHistoryBundle,
  descriptor: OverviewMetricGraphDescriptor
): ProjectedMetricTraces {
  const rollup = bundle.rolling_5m?.[descriptor.metric];
  const raw = validSamples(bundle.series?.[descriptor.metric]);
  const aggregateAvailable = rollup?.state === 'available';
  const min = aggregateAvailable ? validSamples(rollup.min) : [];
  const avg = aggregateAvailable ? validSamples(rollup.avg) : [];
  const max = aggregateAvailable ? validSamples(rollup.max) : [];
  const sampledTimes = [
    ...new Set([...raw, ...min, ...avg, ...max].map(([time]) => time)),
  ].sort((left, right) => left - right);
  // A midpoint is a break marker, not a measurement. A missing poll must not
  // join two otherwise adjacent samples into a continuous line.
  const times: number[] = [];
  const suppressed = new Set<number>();
  for (const time of sampledTimes) {
    const previous = times[times.length - 1];
    if (
      Number.isFinite(bundle.step_seconds) &&
      bundle.step_seconds > 0 &&
      previous !== undefined &&
      time - previous > bundle.step_seconds * 1.5
    ) {
      const difference = time - previous;
      const marker = Number.isFinite(difference)
        ? previous + difference / 2
        : previous / 2 + time / 2;
      if (Number.isFinite(marker) && previous < marker && marker < time) {
        times.push(marker);
      } else {
        // No representable null-only timestamp: drop the earlier value so
        // a chart cannot draw a line across the missing interval.
        suppressed.add(previous);
      }
    }
    times.push(time);
  }
  const at = (samples: OverviewHistorySample[]): (number | null)[] => {
    const byTime = new Map(samples);
    return times.map((time) =>
      suppressed.has(time) ? null : (byTime.get(time) ?? null)
    );
  };
  const observed = at(raw);
  // Range-query times are evaluation coordinates, not acquisition timestamps.
  // Old trailing statistics cannot supply a present missing raw observation.
  const aggregate = (samples: OverviewHistorySample[]) =>
    at(samples).map((value, index) =>
      observed[index] === null ? null : value
    );
  return {
    state: !aggregateAvailable
      ? 'unavailable'
      : sampledTimes.length
        ? 'available'
        : 'empty',
    times,
    observed,
    min: aggregate(min),
    avg: aggregate(avg),
    max: aggregate(max),
  };
}

/** Compatibility projection for consumers that also need a wall-clock edge. */
export function projectMetricHistory(
  bundle: OverviewHistoryBundle,
  descriptor: OverviewMetricGraphDescriptor,
  nowMs: number
): ProjectedMetricHistory {
  return {
    ...projectMetricTraces(bundle, descriptor),
    visibleRightSeconds: Math.max(
      bundle.start_timestamp_seconds,
      Math.min(bundle.end_timestamp_seconds, nowMs / 1000 - 7.5)
    ),
  };
}
