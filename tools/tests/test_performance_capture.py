"""Exercise capture's real event boundary without a browser or external services."""

import subprocess
import unittest
from pathlib import Path

CAPTURE = Path(__file__).parents[1] / "acceptance/performance/capture.mjs"
PRELUDE = r"""
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { createHash } from 'node:crypto';
const { createApiCapture, identityFromHealth } = await import(process.argv[2]);
let now = 10;
const rows = [];
const capture = createApiCapture({append: (file, row) => rows.push({file, ...row}), clock: () => now});
const page = new EventEmitter();
page.url = () => 'http://fixture/operator';
capture.attach(page, 1);
const health = {store_id:'store-a', api_epoch:'epoch-a', source_mode:'simulation',
  simulation_run_id:'run-a', mission_journal:true, operating_context_id:'context-a', replay_run_id:null};
function request(path, method='GET') {
  const req = {url: () => 'http://fixture'+path, method: () => method,
    frame: () => ({url: () => 'http://fixture/operator'}),
    failure: () => req.failureValue, response: async () => req.res ?? null};
  page.emit('request', req);
  return req;
}
function response(req, status, value, options={}) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : JSON.stringify(value));
  const res = {request: () => req, status: () => status,
    headers: () => ({'content-type':'application/json', ...(options.headers ?? {})}),
    body: options.body ?? (async () => bytes)};
  req.res = res;
  page.emit('response', res);
  return res;
}
const terminals = () => rows.filter(row => row.event === 'terminal');
const tick = () => new Promise(resolve => setImmediate(resolve));
capture.phase('measured');
"""


# Each scenario protects a distinct failure of the evidence/qualification contract.
SCENARIOS = {
    "409_body_is_classified_but_still_fatal": r"""
const identity = '["store-a","epoch-a","simulation","context-a"]';
const req = request('/api/v2/operator/records?mission_id=mission-a&scope=leg&leg_id=leg-1&source_identity='+encodeURIComponent(identity));
const body = {error:{code:'store_context_changed', retryable:false}, request_id:'request-a'};
response(req,409,body); page.emit('requestfinished',req);
await capture.drain(100);
const row=terminals()[0];
assert.equal(row.outcome,'http_error');
assert.equal(row.classification,'store_context_changed');
assert.equal(row.sourceIdentity,identity);
assert.equal(row.query.leg_id,'leg-1');
assert.equal(row.body.text,JSON.stringify(body));
assert.equal(row.body.bytes,Buffer.byteLength(JSON.stringify(body)));
assert.equal(row.body.sha256,createHash('sha256').update(JSON.stringify(body)).digest('hex'));
assert.equal(row.body.truncated,false);
assert.equal(capture.summary().phases.measured.http_errors,1);
assert.equal(capture.summary().qualification_clean,false);
assert.throws(()=>capture.assertHealthy(),/HTTP|http/);
""",
    "successful_record_body_retains_source_without_journal_payload": r"""
const req=request('/api/v2/operator/records?mission_id=mission-a');
response(req,200,{source:health,items:[{note:'NEVER RETAIN THIS JOURNAL PAYLOAD'}]});
page.emit('requestfinished',req); now=12; await capture.drain(100);
const row=terminals()[0];
assert.equal(row.outcome,'success');
assert.equal(row.responseSourceIdentity,'["store-a","epoch-a","simulation","context-a"]');
assert.equal(JSON.stringify(rows).includes('NEVER RETAIN'),false);
assert.equal(row.body.text,undefined);
assert.deepEqual(capture.snapshot(1).lastRecordCompletion,{id:row.id,at:12,
  sourceIdentity:'["store-a","epoch-a","simulation","context-a"]',status:200});
assert.equal(capture.snapshot(1).inflight,0);
assert.equal(capture.snapshot(1).idleSince,12);
assert.equal(capture.summary().qualification_clean,true);
""",
    "health_and_context_snapshots_use_actual_bodies": r"""
const req=request('/api/v2/operator/health'); response(req,200,health); page.emit('requestfinished',req);
const ctx=request('/api/v2/operator/context');
response(ctx,200,{state:'available',mission_id:'mission-a',operating_context_id:'context-a'});
page.emit('requestfinished',ctx); await capture.drain(100);
const state=capture.snapshot(1);
assert.deepEqual(state.lastHealthCompletion,{id:terminals()[0].id,at:10,status:200,
  identity:'["store-a","epoch-a","simulation","context-a"]'});
assert.deepEqual(state.lastContextCompletion,{id:terminals()[1].id,at:10,status:200,
  missionId:'mission-a',operatingContextId:'context-a'});
assert.equal(identityFromHealth({...health,operating_context_id:null,replay_run_id:'replay-b'}),'["store-a","epoch-a","simulation","replay-b"]');
assert.equal(identityFromHealth({...health,operating_context_id:null}),'["store-a","epoch-a","simulation","idle:run-a"]');
assert.equal(identityFromHealth({...health,mission_journal:false}),'["store-a","epoch-a","simulation","run-a"]');
""",
    "measured_cancel_stays_fatal_even_after_explicit_teardown": r"""
const req=request('/api/v2/operator/record-changes?mission_id=mission-a&after_seq=2');
capture.phase('post'); capture.phase('teardown');
req.failureValue={errorText:'net::ERR_ABORTED'}; page.emit('requestfailed',req);
await capture.drain(100);
assert.equal(terminals()[0].outcome,'client_cancellation');
assert.equal(terminals()[0].startedPhase,'measured');
assert.equal(terminals()[0].terminalPhase,'teardown');
assert.equal(capture.summary().phases.measured.cancellations,1);
assert.equal(capture.summary().qualification_clean,false);
assert.throws(()=>capture.assertHealthy(),/cancel/);
""",
    "network_error_is_not_a_cancellation": r"""
const req=request('/api/status');req.failureValue={errorText:'net::ERR_CONNECTION_RESET'};
page.emit('requestfailed',req);await capture.drain(100);
assert.equal(terminals()[0].outcome,'network_error');
assert.equal(terminals()[0].errorText,'net::ERR_CONNECTION_RESET');
assert.equal(capture.summary().phases.measured.network_errors,1);
assert.equal(capture.summary().qualification_clean,false);
assert.throws(()=>capture.assertHealthy(),/network/);
""",
    "oversize_body_is_bounded_and_fails_capture": r"""
const req=request('/api/v2/operator/records');
response(req,409,Buffer.alloc(65537,97));page.emit('requestfinished',req);
await capture.drain(100);
assert.equal(Buffer.byteLength(terminals()[0].body.text),65536);
assert.equal(terminals()[0].body.truncated,true);
assert.ok(terminals()[0].body.error);
assert.ok(capture.summary().capture_errors>0);
assert.throws(()=>capture.assertHealthy(),/capture|observer/);
""",
    "body_rejection_or_malformed_source_fails_capture": r"""
const req=request('/api/v2/operator/health');
response(req,200,health,{body:async()=>{throw Error('body unavailable')}});page.emit('requestfinished',req);
const bad=request('/api/v2/operator/records');response(bad,200,'{not-json');page.emit('requestfinished',bad);
await capture.drain(100);
assert.equal(terminals().length,2);
assert.ok(terminals().every(row=>row.body.error));
assert.equal(capture.summary().capture_errors,2);
assert.equal(capture.summary().qualification_clean,false);
""",
    "inflight_is_healthy_until_drain_requires_completeness": r"""
request('/api/status');
assert.doesNotThrow(()=>capture.assertHealthy());
assert.equal(capture.snapshot(1).inflight,1);
assert.equal(capture.snapshot(1).idleSince,null);
assert.equal(capture.summary().qualification_clean,false);
await assert.rejects(capture.drain(10),/drain|unfinished|timeout/i);
assert.equal(capture.summary().phases.measured.inflight,1);
assert.ok(capture.summary().capture_errors>0);
""",
    "pending_body_is_inflight_until_late_completion": r"""
let release;
const req=request('/api/v2/operator/health');
response(req,200,health,{body:()=>new Promise(resolve=>{release=resolve})});page.emit('requestfinished',req);
await tick();assert.equal(capture.snapshot(1).inflight,1);
assert.equal(capture.snapshot(1).lastHealthCompletion,null);
now=15;release(Buffer.from(JSON.stringify(health)));await capture.drain(100);
assert.equal(capture.snapshot(1).inflight,0);
assert.equal(capture.snapshot(1).lastHealthCompletion.at,15);
assert.equal(terminals().length,1);
""",
    "duplicate_terminal_events_do_not_duplicate_evidence": r"""
const req=request('/api/status');response(req,200,{});
page.emit('requestfinished',req);page.emit('requestfinished',req);page.emit('requestfailed',req);
await capture.drain(100);
assert.equal(rows.filter(row=>row.event==='start').length,1);
assert.equal(terminals().length,1);
assert.equal(capture.summary().phases.measured.terminal,1);
assert.equal(capture.summary().phases.measured.inflight,0);
assert.equal(rows.every(row=>row.file==='api-outcomes.jsonl'),true);
""",
    "gps_exception_is_exact_and_other_503_is_fatal": r"""
const gps=request('/api/v2/gps/config');response(gps,503,{detail:'GPS unavailable'});page.emit('requestfinished',gps);
await capture.drain(100);
assert.equal(capture.summary().phases.measured.allowedGPS503,1);
assert.equal(capture.summary().qualification_clean,true);
const req=request('/api/v2/operator/health');response(req,503,{error:{code:'store_unavailable'}});page.emit('requestfinished',req);
await capture.drain(100);
assert.equal(capture.summary().phases.measured.http_errors,1);
assert.equal(capture.summary().qualification_clean,false);
""",
    "unmatched_api_terminal_cannot_look_complete": r"""
const req={url:()=> 'http://fixture/api/status'};
page.emit('requestfinished',req);await tick();
assert.equal(capture.summary().unknown_terminal,1);
assert.equal(capture.summary().qualification_clean,false);
assert.throws(()=>capture.assertHealthy(),/capture|observer|unknown/);
""",
    "stop_refuses_any_active_request_then_detaches_at_capture_fence": r"""
const req=request('/api/status');
assert.throws(()=>capture.stop(),/inflight|unfinished|active/);
response(req,200,{});page.emit('requestfinished',req);await capture.drain(100);
now=20;capture.phase('post');capture.stop();capture.stop();
const ends=rows.filter(row=>row.event==='capture-end');
assert.equal(ends.length,1);assert.equal(ends[0].at,20);
assert.equal(page.listenerCount('request'),0);
assert.equal(page.listenerCount('response'),0);
assert.equal(page.listenerCount('requestfinished'),0);
assert.equal(page.listenerCount('requestfailed'),0);
request('/api/status');assert.equal(rows.filter(row=>row.event==='start').length,1);
assert.equal(capture.summary().qualification_clean,true);
""",
    "stop_rejects_pending_body_and_unmeasured_active_requests": r"""
capture.phase('warmup');const warm=request('/api/status');
assert.throws(()=>capture.stop(),/inflight|unfinished|active/);
response(warm,200,{});page.emit('requestfinished',warm);await tick();
capture.phase('measured');let release;
const req=request('/api/v2/operator/health');
response(req,200,health,{body:()=>new Promise(resolve=>{release=resolve})});page.emit('requestfinished',req);
await tick();assert.throws(()=>capture.stop(),/inflight|unfinished|active/);
release(Buffer.from(JSON.stringify(health)));await capture.drain(100);
capture.stop();assert.equal(rows.filter(row=>row.event==='capture-end').length,1);
""",
    "advertised_oversize_is_rejected_before_body_retrieval": r"""
const req=request('/api/v2/operator/records');
response(req,409,{}, {headers:{'content-length':'1000000000'},
  body:async()=>{throw Error('must not retrieve advertised oversized body')}});
page.emit('requestfinished',req);await capture.drain(100);
assert.equal(terminals()[0].body.truncated,true);
assert.equal(terminals()[0].body.declaredBytes,1000000000);
assert.match(terminals()[0].body.error,/Content-Length/);
assert.equal(capture.summary().capture_errors,1);
""",
    "late_completion_cannot_clear_a_failed_drain": r"""
let release;const req=request('/api/v2/operator/health');
response(req,200,health,{body:()=>new Promise(resolve=>{release=resolve})});page.emit('requestfinished',req);
await assert.rejects(capture.drain(10),/timeout/);
release(Buffer.from(JSON.stringify(health)));await capture.drain(100);
assert.equal(terminals().length,1);assert.equal(capture.snapshot(1).inflight,0);
assert.equal(capture.summary().qualification_clean,false);
assert.throws(()=>capture.assertHealthy(),/capture|observer/);
""",
    "body_timeout_produces_terminal_capture_failure": r"""
const req=request('/api/v2/operator/health');
response(req,200,health,{body:()=>new Promise(()=>{})});page.emit('requestfinished',req);
await capture.drain(6000);
assert.equal(terminals().length,1);assert.match(terminals()[0].body.error,/timeout/);
assert.equal(capture.summary().phases.measured.inflight,0);
assert.equal(capture.summary().qualification_clean,false);
""",
    "broken_evidence_sink_is_fatal_even_if_network_succeeds": r"""
const broken=createApiCapture({append:()=>{throw Error('disk full')},clock:()=>now});
const second=new EventEmitter();second.url=()=> 'http://fixture/operator';broken.attach(second,0);broken.phase('measured');
const req={url:()=> 'http://fixture/api/status',method:()=> 'GET',frame:()=>null};
second.emit('request',req);
const res={request:()=>req,status:()=>200};second.emit('response',res);second.emit('requestfinished',req);
await broken.drain(100);assert.equal(broken.summary().phases.measured.terminal,1);
assert.equal(broken.summary().capture_errors,2);assert.equal(broken.summary().qualification_clean,false);
""",
    "missing_simulation_identity_cannot_be_invented": r"""
const req=request('/api/v2/operator/health');
response(req,200,{...health,operating_context_id:null,simulation_run_id:undefined});page.emit('requestfinished',req);
await capture.drain(100);
assert.equal(capture.summary().qualification_clean,false);
assert.match(terminals()[0].body.error,/identity/);
""",
}


class CaptureTests(unittest.TestCase):
    pass


def scenario_test(scenario):
    def exercise(self):
        result = subprocess.run(
            ["node", "--input-type=module", "-", str(CAPTURE)],
            input=PRELUDE + SCENARIOS[scenario],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    return exercise


for name in SCENARIOS:
    setattr(CaptureTests, "test_" + name, scenario_test(name))


if __name__ == "__main__":
    unittest.main()
