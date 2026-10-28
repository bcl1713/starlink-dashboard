"""Mission controls wait for actual read completion without pausing UI polling."""

import subprocess
from pathlib import Path


def test_operator_controls_require_fresh_idle_reads_and_reconciled_identity():
    module = (
        Path(__file__).resolve().parents[1] / "acceptance/performance/coordination.mjs"
    )
    program = r"""
import assert from 'node:assert/strict';
const { waitForReadBoundary, waitForSource, waitForAllIdle } = await import(process.argv[1]);
function fixture(states, failed = false) {
  let step = 0;
  return {
    capture: {
      snapshot: () => states[Math.min(step, states.length - 1)],
      assertHealthy: () => { if (failed) throw new Error('measured failure'); },
    },
    options: { clock: () => step * 0.025, sleep: async () => { step++; }, timeoutMs: 250, idleMs: 50 },
  };
}
const state = (overrides = {}) => ({ inflight: 0, idleSince: 0,
  lastRecordCompletion: { id: 1, status: 200, sourceIdentity: 'old' },
  lastContextCompletion: { id: 2, status: 200, missionId: 'synthetic-mission-a' },
  lastHealthCompletion: { id: 3, status: 200, identity: 'old' }, ...overrides });
let f = fixture([state(), state({ inflight: 1 }), state({ lastRecordCompletion: { id: 4, status: 200, sourceIdentity: 'old' }, idleSince: 0.05 })]);
const boundary = await waitForReadBoundary(f.capture, 1, { ...f.options, recordsActive: true });
assert.equal(boundary.request_id, 4);
assert.ok(boundary.observed_idle_ms >= 50);
f = fixture([state()]);
await assert.rejects(waitForReadBoundary(f.capture, 1, { ...f.options, recordsActive: true }), /boundary.*timeout/);
f = fixture([state(), state({ inflight: 1, lastRecordCompletion: { id: 4, status: 200, sourceIdentity: 'old' } })]);
await assert.rejects(waitForReadBoundary(f.capture, 1, { ...f.options, recordsActive: true }), /boundary.*timeout/);
f = fixture([state()], true);
await assert.rejects(waitForReadBoundary(f.capture, 1, { ...f.options, recordsActive: true }), /measured failure/);
const fresh = state({ lastRecordCompletion: { id: 4, status: 200, sourceIdentity: 'new' },
  lastHealthCompletion: { id: 5, status: 200, identity: 'new' } });
f = fixture([state(), fresh]);
await waitForSource(f.capture, 1, { ...f.options, identity: 'new', recordsActive: true, missionId: 'synthetic-mission-a' });
f = fixture([state({ lastHealthCompletion: { id: 5, status: 200, identity: 'new' } })]);
await assert.rejects(waitForSource(f.capture, 1, { ...f.options, identity: 'new', recordsActive: true, missionId: 'synthetic-mission-a' }), /source.*timeout/);
f = fixture([state({ lastHealthCompletion: { id: 5, status: 200, identity: 'new' }, lastContextCompletion: { id: 6, status: 200, missionId: null } })]);
await waitForSource(f.capture, 1, { ...f.options, identity: 'new', recordsActive: false, missionId: 'synthetic-mission-a' });
f = fixture([state({ inflight: 1 }), state()]);
await waitForAllIdle(f.capture, 2, f.options);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program, module.as_uri()],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
