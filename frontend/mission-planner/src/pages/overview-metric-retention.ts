import type {
  OverviewHistoryBundle,
  OverviewHistorySample,
} from '../services/overview-history';
import type { OverviewMetricGraphDescriptor } from './overview-metric-history';

const LEFT_MARGIN_SECONDS = 7.5;
// The shared API caps each trace at 1,801 samples; allow the additional
// seven-and-a-half-second real-sample reserve without unbounded uptime growth.
const MAX_TRACE_SAMPLES = 1820;

export interface RetainedMetricHistory {
  bundle: OverviewHistoryBundle;
}

type Trace = 'observed' | 'min' | 'avg' | 'max';

function samples(
  bundle: OverviewHistoryBundle | undefined,
  metric: string,
  trace: Trace
): OverviewHistorySample[] {
  if (!bundle) return [];
  const rollup = bundle.rolling_5m?.[metric];
  const entries =
    trace === 'observed'
      ? bundle.series?.[metric]
      : rollup?.state === 'available'
        ? rollup[trace]
        : [];
  return Array.isArray(entries)
    ? entries.filter(
        (sample) =>
          Array.isArray(sample) &&
          sample.length === 2 &&
          Number.isFinite(sample[0]) &&
          Number.isFinite(sample[1])
      )
    : [];
}

/** Retain only chart samples outside the newer bundle's authoritative range. */
export function retainMetricHistory(
  previous: RetainedMetricHistory | undefined,
  incoming: OverviewHistoryBundle,
  descriptor: OverviewMetricGraphDescriptor
): RetainedMetricHistory {
  const prior =
    previous?.bundle.window_seconds === incoming.window_seconds
      ? previous.bundle
      : undefined;
  if (prior && incoming.end_timestamp_seconds < prior.end_timestamp_seconds)
    return previous!;
  const metric = descriptor.metric;
  const lower =
    incoming.end_timestamp_seconds -
    incoming.window_seconds -
    LEFT_MARGIN_SECONDS;
  const merged = (trace: Trace): OverviewHistorySample[] => {
    const older = samples(prior, metric, trace).filter(
      ([time]) => time >= lower && time < incoming.start_timestamp_seconds
    );
    const fresh = samples(incoming, metric, trace).filter(
      ([time]) =>
        time >= incoming.start_timestamp_seconds &&
        time <= incoming.end_timestamp_seconds
    );
    return [
      ...new Map(
        [...older, ...fresh].map((sample) => [sample[0], sample])
      ).values(),
    ]
      .sort(([left], [right]) => left - right)
      .slice(-MAX_TRACE_SAMPLES);
  };
  const rollup = incoming.rolling_5m?.[metric];
  const available = rollup?.state === 'available';
  return {
    bundle: {
      window_seconds: incoming.window_seconds,
      start_timestamp_seconds: incoming.start_timestamp_seconds,
      end_timestamp_seconds: incoming.end_timestamp_seconds,
      step_seconds: incoming.step_seconds,
      // Deliberately never copy the aircraft or other metrics into chart state.
      series: { [metric]: merged('observed') },
      rolling_5m: {
        [metric]: {
          state: available ? 'available' : 'unavailable',
          min: available ? merged('min') : [],
          avg: available ? merged('avg') : [],
          max: available ? merged('max') : [],
        },
      },
    },
  };
}
