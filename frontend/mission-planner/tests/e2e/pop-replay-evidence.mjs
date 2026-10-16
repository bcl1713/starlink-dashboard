/** Independent HTTP observation checks; no interpolation of unobserved positions. */
import assert from 'node:assert/strict';

function angularDistance(position, site) {
  const radians = (value) => (value * Math.PI) / 180;
  const latitude = radians(position.latitude);
  const target = radians(site.latitude);
  return (
    1 -
    (Math.sin(latitude) * Math.sin(target) +
      Math.cos(latitude) *
        Math.cos(target) *
        Math.cos(radians(position.longitude - site.longitude)))
  );
}
function publishedClock(sample) {
  // The status and run endpoints are separate requests. Match the acquisition
  // timestamp to an actually published run on either side, never extrapolate it.
  const telemetryAt = Date.parse(sample.status.timestamp);
  const candidates = [sample.runBefore, sample.run].filter(Boolean);
  const match = candidates.find(
    (candidate) =>
      Math.abs(Date.parse(candidate.run.observed_at) - telemetryAt) < 50
  );
  assert.ok(match, 'Telemetry has no matching published run clock');
  return match;
}
export function verifyCrossing(samples, transition, sites) {
  assert.ok(sites.length > 1, 'Captured catalog sites required');
  for (const sample of samples) {
    const nearest = [...sites].sort(
      (left, right) =>
        angularDistance(sample.status.position, left) -
        angularDistance(sample.status.position, right)
    )[0];
    assert.equal(
      sample.status.pop_observation.entry.city,
      nearest.city,
      'Observed IP must follow nearest captured PoP at the observed position'
    );
  }
  const nextIndex = samples.findIndex(
    (sample) =>
      sample.status.pop_observation.entry.city === transition.crossing.to_city
  );
  assert.ok(nextIndex > 0, 'Observed samples must straddle the crossing');
  const before = samples[nextIndex - 1];
  const after = samples[nextIndex];
  assert.equal(
    before.status.pop_observation.entry.city,
    transition.crossing.from_city
  );
  const oldClock = publishedClock(before);
  const newClock = publishedClock(after);
  const lower = Date.parse(oldClock.run.simulation_time);
  const upper = Date.parse(newClock.run.simulation_time);
  const crossing = Date.parse(transition.crossing_utc);
  assert.ok(
    lower <= crossing && crossing <= upper,
    'True crossing must lie in the last-old/first-new publication bracket'
  );
  assert.equal(
    newClock.revision - oldClock.revision,
    1,
    'Switch bracket must span exactly one actual publication'
  );
  return {
    missionUtcBracket: [
      oldClock.run.simulation_time,
      newClock.run.simulation_time,
    ],
    observedUtcBracket: [oldClock.run.observed_at, newClock.run.observed_at],
    publications: newClock.revision - oldClock.revision,
    beforePosition: before.status.position,
    afterPosition: after.status.position,
    crossingUtc: transition.crossing_utc,
  };
}
export function verifyContinuity(sample, endpoint) {
  const continuity = sample.status.call_continuity;
  if (continuity === null) {
    assert.equal(
      sample.run.state,
      'completed',
      'Unresolved continuity during replay'
    );
    assert.equal(sample.status.position.latitude, endpoint.latitude);
    assert.equal(sample.status.position.longitude, endpoint.longitude);
    return;
  }
  assert.ok(continuity, 'Missing continuity evidence');
  assert.equal(continuity.pop_call_outage_seconds, 0);
}
