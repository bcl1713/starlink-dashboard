/** Liveness coverage; configured delay and observed request rate stay separate. */
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
