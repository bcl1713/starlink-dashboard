/** Liveness coverage; configured delay and observed request rate stay separate. */
export function validateHistory(history, window) {
  const step = history.step_seconds;
  if (history.window_seconds !== window || !Number.isInteger(step) || step < 1)
    throw new Error("History window/resolution is invalid");
  const start = history.start_timestamp_seconds;
  const end = history.end_timestamp_seconds;
  if (
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    end - start !== window
  )
    throw new Error("History bounds are invalid");
  const series = Object.values(history.series);
  const points = Math.floor(window / step) + 1;
  if (
    series.length !== 11 ||
    series.some(
      (values) =>
        values.length !== points ||
        values.some(
          (point, index) =>
            point[0] !== start + index * step || !Number.isFinite(point[1]),
        ),
    )
  )
    throw new Error("Synthetic history must have 11 dense finite series");
  return step;
}

export function networkMilliseconds(timing) {
  // Playwright responseEnd is already an offset from its epoch startTime.
  if (!Number.isFinite(timing.responseEnd) || timing.responseEnd < 0)
    throw new Error("Browser network responseEnd is unavailable");
  return timing.responseEnd;
}

export function pollingCovered(subscription, start, end) {
  const tolerance = 5;
  return (
    subscription.starts >= 2 &&
    subscription.successful_completions >=
      Math.max(2, Math.floor((end - start) / tolerance)) &&
    subscription.first !== null &&
    subscription.last !== null &&
    subscription.first >= start &&
    subscription.first - start <= tolerance &&
    end - subscription.last <= tolerance &&
    subscription.last - end <= tolerance &&
    subscription.max_gap_seconds <= tolerance
  );
}
