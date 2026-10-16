import assert from 'node:assert/strict';
import { test } from 'node:test';
import { verifyCrossing, verifyContinuity } from './pop-replay-evidence.mjs';

const sites = [
  { city: 'Tokyo', latitude: 0, longitude: 170 },
  { city: 'Los Angeles', latitude: 0, longitude: -170 },
];
const utc = (seconds) =>
  new Date(Date.UTC(2026, 9, 25, 14, 0, seconds)).toISOString();
const transition = {
  crossing_utc: utc(10),
  crossing: { from_city: 'Tokyo', to_city: 'Los Angeles' },
};
function sample(seconds, city, longitude, revision) {
  const run = {
    state: 'running',
    revision,
    run: {
      simulation_time: utc(seconds),
      observed_at: utc(seconds),
      effective_multiplier: 720,
    },
  };
  return {
    status: {
      timestamp: utc(seconds),
      position: { latitude: 0, longitude },
      pop_observation: { entry: { city } },
      call_continuity: { pop_call_outage_seconds: 0 },
    },
    runBefore: structuredClone(run),
    run,
  };
}
const samples = () => [
  sample(9, 'Tokyo', 179, 20),
  sample(21, 'Los Angeles', -179, 21),
];

test('accepts a true crossing bracket despite sparse accelerated publication', () => {
  const result = verifyCrossing(samples(), transition, sites);
  assert.equal(result.publications, 1);
  assert.deepEqual(result.missionUtcBracket, [utc(9), utc(21)]);
});
for (const damage of [
  'wrong-position',
  'crossing-outside-bracket',
  'skipped-publication',
]) {
  test(`rejects ${damage} rather than loosening crossing timing`, () => {
    const values = samples();
    if (damage === 'wrong-position') values[1].status.position.longitude = 169;
    if (damage === 'crossing-outside-bracket')
      values[0] = sample(11, 'Tokyo', 179, 20);
    if (damage === 'skipped-publication')
      values[1].run.revision = values[1].runBefore.revision = 22;
    assert.throws(() => verifyCrossing(values, transition, sites));
  });
}
test('uses the telemetry publication clock when run GET crosses a tick', () => {
  const values = samples();
  values[0].run = structuredClone(values[1].run);
  assert.deepEqual(
    verifyCrossing(values, transition, sites).missionUtcBracket,
    [utc(9), utc(21)]
  );
});
test('terminal continuity null requires completed run and exact endpoint', () => {
  const value = sample(21, 'Los Angeles', -179, 21);
  value.run.state = 'completed';
  value.status.call_continuity = null;
  verifyContinuity(value, { latitude: 0, longitude: -179 });
  assert.throws(() =>
    verifyContinuity(value, { latitude: 0, longitude: -178 })
  );
  value.run.state = 'running';
  assert.throws(() =>
    verifyContinuity(value, { latitude: 0, longitude: -179 })
  );
});
test('known continuity still proves zero and unknown cannot become zero', () => {
  const value = samples()[0];
  verifyContinuity(value, { latitude: 0, longitude: -179 });
  value.status.call_continuity = { pop_call_outage_seconds: 600 };
  assert.throws(() =>
    verifyContinuity(value, { latitude: 0, longitude: -179 })
  );
});
