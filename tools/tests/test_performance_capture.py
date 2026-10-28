"""Exercise capture's real event boundary without a browser or external services."""

import subprocess
import unittest
from pathlib import Path

CAPTURE = Path(__file__).parents[1] / "acceptance/performance/capture.mjs"
PRELUDE = r"""
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { createHash } from 'node:crypto';
import { runInNewContext } from 'node:vm';
const { createApiCapture, identityFromHealth } = await import(process.argv[2]);
let now = 10;
const rows = [];
const capture = createApiCapture({append: (file, row) => rows.push({file, ...row}), clock: () => now});
const page = new EventEmitter();
page.url = () => 'http://fixture/operator';
capture.attach(page, 1);
const health = {store_id:'store-a', api_epoch:'epoch-a', source_mode:'simulation',
  simulation_run_id:'run-a', mission_journal:true, operating_context_id:'context-a', replay_run_id:null};
function request(path, method='GET', redirectedFrom=null, options={}) {
  const req = {url: () => 'http://fixture'+path, method: () => method,
    redirectedFrom: () => redirectedFrom,
    resourceType: () => options.resourceType ?? 'xhr', timing: () => ({startTime: options.startTime ?? 1000}),
    frame: () => ({url: () => 'http://fixture/operator'}),
    failure: () => req.failureValue, response: async () => req.res ?? null};
  page.emit('request', req);
  if (page.cdpSession && options.cdp !== false)
    page.cdpSession.emit('Network.requestWillBeSent',{requestId:'cdp-'+(++page.cdpSequence),
      wallTime:options.cdpWallTime ?? ((options.startTime ?? 1000)/1000),
      request:{url:req.url(),method:req.method()}});
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
async function installAbortHook() {
  page.cdpSequence=0;page.cdpSession=new EventEmitter();
  page.cdpSession.send=async()=>{};page.cdpSession.detach=async()=>{};
  page.context=()=>({newCDPSession:async()=>page.cdpSession});
  page.exposeBinding=async(name,callback)=>{page.abortBinding=callback;page.abortBindingName=name};
  page.addInitScript=async(fn,arg)=>{page.abortInit=fn;page.abortInitArg=arg};
  return capture.observeClientAborts(page,1);
}
function proofFor(requestId,abortId='p1-a-probe') {
  return {protocol:'issue393-client-abort-v2',clean:true,source_sha256:'a'.repeat(64),
    input_sha256:{api:'b'.repeat(64),abort:'c'.repeat(64),transition:'d'.repeat(64)},
    expected:[{request_id:requestId,abort_id:abortId,transition_id:'transition-0',page:1,
      recovery_ids:{health:'health-1',context:'context-1',fresh_source:'events-1',
        operator_health:'health-2',operator_context:'context-2',operator_records:null},proof:{}}],unexpected:[]};
}
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
    "canonical_redirect_chain_records_location_without_reading_protocol_body": r"""
for (const status of [301,302,303,307,308]) {
  const previous=terminals().length;
  const initial=request('/api/routes?redirect_test='+status);
  response(initial,status,null,{headers:{location:'/api/routes/?redirect_test='+status},
    body:async()=>{throw Error('Response body is unavailable for redirect responses')}});
  page.emit('requestfinished',initial);
  const followed=request('/api/routes/?redirect_test='+status,'GET',initial);
  response(followed,200,{routes:[]});page.emit('requestfinished',followed);
  await capture.drain(100);
  const redirect=terminals().slice(previous).find(row=>row.status===status);
  const success=terminals().slice(previous).find(row=>row.status===200);
  assert.equal(redirect.status,status);
  assert.equal(redirect.outcome,'redirect');
  assert.equal(redirect.classification,'http_redirect');
  assert.equal(redirect.redirectLocation,'/api/routes/?redirect_test='+status);
  assert.equal(redirect.body.unavailableByProtocol,true);
  assert.equal(redirect.body.notCapturedReason,'chromium_redirect_body_unavailable');
  assert.equal(redirect.body.bytes,null);assert.equal(redirect.body.sha256,null);
  assert.equal(redirect.body.text,undefined);assert.equal(redirect.body.error,null);
  assert.equal(success.outcome,'success');
  assert.equal(success.redirectedFromId,redirect.id);
  assert.equal(rows.find(row=>row.event==='start'&&row.id===success.id).redirectedFromId,redirect.id);
}
assert.equal(capture.summary().phases.measured.started,10);
assert.equal(capture.summary().phases.measured.terminal,10);
assert.equal(capture.summary().phases.measured.http_errors,0);
assert.equal(capture.summary().capture_errors,0);
assert.equal(capture.summary().qualification_clean,true);
assert.doesNotThrow(()=>capture.assertHealthy());
""",
    "redirect_without_location_cannot_look_like_complete_capture": r"""
const req=request('/api/routes');
response(req,307,null,{body:async()=>{throw Error('must not request redirect body')}});
page.emit('requestfinished',req);await capture.drain(100);
assert.equal(capture.summary().capture_errors,1);
assert.equal(capture.summary().qualification_clean,false);
assert.match(terminals()[0].body.error,/Location/);
assert.throws(()=>capture.assertHealthy(),/capture|observer/);
""",
    "location_header_does_not_hide_http_errors_or_other_body_failures": r"""
const conflict=request('/api/v2/operator/records');
response(conflict,409,{error:{code:'store_context_changed'}},{headers:{location:'/api/routes/'}});
page.emit('requestfinished',conflict);await capture.drain(100);
assert.equal(terminals()[0].outcome,'http_error');
assert.equal(terminals()[0].classification,'store_context_changed');
assert.ok(terminals()[0].body.text);
assert.equal(capture.summary().phases.measured.http_errors,1);
const notModified=request('/api/routes');
response(notModified,304,null,{headers:{location:'/api/routes/'},
  body:async()=>{throw Error('ordinary body retrieval failure')}});
page.emit('requestfinished',notModified);await capture.drain(100);
assert.equal(capture.summary().capture_errors,1);
assert.match(terminals()[1].body.error,/ordinary body retrieval failure/);
assert.equal(capture.summary().qualification_clean,false);
""",
    "event_and_context_metadata_bind_real_response_source_and_wall_clocks": r"""
const req=request('/api/v2/operator/events?mission_id=mission-a&include_history=true');
response(req,200,{store_id:'store-a',api_epoch:'epoch-a',source_mode:'simulation',
  simulation_run_id:'context-a',mission_id:'mission-a',events:[{title:'PRIVATE EVENT PAYLOAD'}]});
page.emit('requestfinished',req);await capture.drain(100);
const row=terminals()[0];
assert.deepEqual(row.eventSource,{identity:'["store-a","epoch-a","simulation","context-a"]',missionId:'mission-a'});
assert.equal(row.resourceType,'xhr');assert.equal(row.wallStartTimeMs,1000);
assert.ok(Number.isFinite(row.wallTimeMs));assert.equal(row.body.text,undefined);
assert.equal(JSON.stringify(rows).includes('PRIVATE EVENT PAYLOAD'),false);
const ctx=request('/api/v2/operator/context');
response(ctx,200,{mission_id:'mission-a',operating_context_id:'context-a'});page.emit('requestfinished',ctx);
await capture.drain(100);
assert.deepEqual(terminals()[1].context,{missionId:'mission-a',operatingContextId:'context-a'});
""",
    "xhr_hook_records_actual_abort_and_preserves_native_calls_and_exceptions": r"""
assert.equal(await installAbortHook(),true);
const sentinel=Error('native abort exception');
class NativeXHR {
  open(...args){this.openArgs=args;return 'opened'}
  send(...args){this.sendArgs=args;return 'sent'}
  abort(...args){this.abortArgs=args;if(this.throwAbort)throw sentinel;return 'aborted'}
}
let wall=5;
const realm={XMLHttpRequest:NativeXHR,URL,location:{href:'http://fixture/operator'},
  performance:{timeOrigin:1000,now:()=>wall},
  [page.abortBindingName]:(value)=>Promise.resolve(page.abortBinding({page},value))};
runInNewContext('('+page.abortInit.toString()+')(arg)',{...realm,arg:page.abortInitArg});
const xhr=new NativeXHR();
assert.equal(xhr.open('get','/api/v2/operator/events?mission_id=mission-a',true),'opened');
assert.equal(xhr.send(null),'sent');wall=12;
assert.equal(xhr.abort('original-argument'),'aborted');await tick();
const aborts=rows.filter(row=>row.file==='client-aborts.jsonl');
assert.equal(aborts.length,1);assert.equal(aborts[0].mechanism,'xhr.abort');
assert.equal(aborts[0].method,'GET');assert.equal(aborts[0].page,1);
assert.equal(aborts[0].url,'http://fixture/api/v2/operator/events?mission_id=mission-a');
assert.equal(aborts[0].sendWallTimeMs,1005);assert.equal(aborts[0].abortWallTimeMs,1012);
assert.deepEqual(xhr.abortArgs,['original-argument']);assert.deepEqual(xhr.sendArgs,[null]);
xhr.throwAbort=true;assert.throws(()=>xhr.abort(),error=>error===sentinel);await tick();
assert.equal(rows.filter(row=>row.file==='client-aborts.jsonl').length,1);
const other=new NativeXHR();other.open('GET','/outside-api');other.send();other.abort();await tick();
assert.equal(rows.filter(row=>row.file==='client-aborts.jsonl').length,1);
capture.stop();xhr.throwAbort=false;xhr.abort();await tick();
assert.equal(rows.filter(row=>row.file==='client-aborts.jsonl').length,1);
""",
    "planned_cancellation_requires_actual_abort_and_complete_scoped_proof": r"""
await installAbortHook();
capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const req=request('/api/v2/operator/events?mission_id=mission-a&include_history=true');
await page.abortBinding({page},{id:'a-probe',url:req.url(),method:'GET',sendWallTimeMs:1000,abortWallTimeMs:1010,mechanism:'xhr.abort'});
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(100);
assert.doesNotThrow(()=>capture.assertHealthy());
assert.equal(capture.summary().qualification_clean,false);
assert.equal(capture.summary().unexpected_cancellations,1);
const proof=proofFor(terminals()[0].id);
capture.applyCancellationQualification(proof);
assert.equal(capture.summary().phases.measured.cancellations,1);
assert.equal(capture.summary().expected_control_cancellations,1);
assert.equal(capture.summary().unexpected_cancellations,0);
assert.equal(capture.summary().qualification_clean,true);
""",
    "proof_cannot_approve_unplanned_wrong_scope_or_duplicate_cancellations": r"""
const req=request('/api/v2/operator/events?mission_id=other-mission');
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(100);
const proof=proofFor(terminals()[0].id);
assert.throws(()=>capture.applyCancellationQualification(proof),/qualification|scope|transition|abort/i);
assert.throws(()=>capture.assertHealthy(),/cancellation/);
assert.equal(capture.summary().qualification_clean,false);
""",
    "planned_scope_cap_and_resource_type_still_fail_fast": r"""
capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const first=request('/api/v2/operator/events?mission_id=mission-a');
first.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',first);await capture.drain(100);
assert.doesNotThrow(()=>capture.assertHealthy());
const second=request('/api/v2/operator/events?mission_id=mission-a');
second.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',second);await capture.drain(100);
assert.throws(()=>capture.assertHealthy(),/cancellation/);
""",
    "malformed_or_missing_proof_never_clears_deferred_cancellation": r"""
await installAbortHook();capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const req=request('/api/v2/operator/events?mission_id=mission-a');
await page.abortBinding({page},{id:'a-probe',url:req.url(),method:'GET',sendWallTimeMs:1000,abortWallTimeMs:1010,mechanism:'xhr.abort'});
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(100);
const valid=proofFor(terminals()[0].id);
for(const change of [
  {protocol:'v1'},{clean:false},{expected:[]},{expected:[...valid.expected,...valid.expected]},
  {unexpected:[{request_id:terminals()[0].id}]},{source_sha256:'unhashed'},
  {expected:[{...valid.expected[0],transition_id:'not-planned'}]},
  {expected:[{...valid.expected[0],abort_id:'unobserved-abort'}]},
  {expected:[{...valid.expected[0],page:0}]},
]) {
 assert.throws(()=>capture.applyCancellationQualification({...valid,...change}),/qualification|proof|scope|transition|abort/i);
 assert.equal(capture.summary().qualification_clean,false);
}
capture.applyCancellationQualification(valid);assert.equal(capture.summary().qualification_clean,true);
""",
    "observer_installation_and_abort_sink_failures_are_fatal": r"""
page.exposeBinding=async()=>{throw Error('binding unavailable')};
await assert.rejects(capture.observeClientAborts(page,1),/binding unavailable/);
assert.throws(()=>capture.assertHealthy(),/capture|observer/);
""",
    "known_abort_from_another_request_cannot_approve_a_cancellation": r"""
await installAbortHook();capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const req=request('/api/v2/operator/events?mission_id=mission-a');
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(100);
for (const [id,change] of [
 ['wrong-url',{url:'http://fixture/api/v2/operator/events?mission_id=other'}],
 ['wrong-method',{method:'POST'}],['wrong-send',{sendWallTimeMs:1200,abortWallTimeMs:1210}],
 ['after-terminal',{abortWallTimeMs:Date.now()+10000}],
]) {
 await page.abortBinding({page},{id,url:req.url(),method:'GET',sendWallTimeMs:1000,abortWallTimeMs:1010,mechanism:'xhr.abort',...change});
 assert.throws(()=>capture.applyCancellationQualification(proofFor(terminals()[0].id,'p1-'+id)),/qualification|abort|proof/i);
 assert.equal(capture.summary().qualification_clean,false);
}
""",
    "non_xhr_or_outside_transition_window_cancel_cannot_be_deferred": r"""
capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const req=request('/api/v2/operator/events?mission_id=mission-a','GET',null,{resourceType:'fetch'});
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(100);
assert.throws(()=>capture.assertHealthy(),/cancellation/);
assert.equal(capture.summary().qualification_clean,false);
""",
    "cdp_wall_time_proves_cancellation_when_playwright_timing_is_initially_zero": r"""
await installAbortHook();capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const req=request('/api/v2/operator/events?mission_id=mission-a','GET',null,{startTime:0,cdpWallTime:1});
await page.abortBinding({page},{id:'a-probe',url:req.url(),method:'GET',sendWallTimeMs:1000,abortWallTimeMs:1010,mechanism:'xhr.abort'});
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(100);
assert.equal(terminals()[0].wallStartTimeMs,1000);
assert.equal(terminals()[0].wallStartTimeSource,'cdp');
assert.equal(terminals()[0].cdpRequestId,'cdp-1');
capture.applyCancellationQualification(proofFor(terminals()[0].id));
assert.equal(capture.summary().qualification_clean,true);
capture.stop();await capture.drain(100);
assert.equal(page.cdpSession.listenerCount('Network.requestWillBeSent'),0);
""",
    "late_cdp_join_keeps_same_url_requests_in_original_network_order": r"""
await installAbortHook();
const one=request('/api/status','GET',null,{startTime:0,cdp:false});
const two=request('/api/status','GET',null,{startTime:0,cdp:false});
response(one,200,{});page.emit('requestfinished',one);
response(two,200,{});page.emit('requestfinished',two);
await tick();
page.cdpSession.emit('Network.requestWillBeSent',{requestId:'net-1',wallTime:2,request:{url:one.url(),method:'GET'}});
page.cdpSession.emit('Network.requestWillBeSent',{requestId:'net-2',wallTime:3,request:{url:two.url(),method:'GET'}});
await capture.drain(100);
const sorted=terminals().sort((a,b)=>a.id.localeCompare(b.id));
assert.equal(sorted[0].wallStartTimeMs,2000);assert.equal(sorted[0].cdpRequestId,'net-1');
assert.equal(sorted[1].wallStartTimeMs,3000);assert.equal(sorted[1].cdpRequestId,'net-2');
capture.stop();await capture.drain(100);
""",
    "unpaired_cdp_cancellation_remains_an_observer_failure": r"""
await installAbortHook();capture.beginTransition({id:'transition-0',operation:0,at:10,missionId:'mission-a'});
const req=request('/api/v2/operator/events?mission_id=mission-a','GET',null,{cdp:false,startTime:0});
req.failureValue={errorText:'net::ERR_ABORTED'};page.emit('requestfailed',req);await capture.drain(1000);
assert.ok(capture.summary().capture_errors>0);
assert.equal(capture.summary().qualification_clean,false);
assert.throws(()=>capture.assertHealthy(),/capture|observer/);
""",
    "xhr_abort_during_native_send_is_observed_without_changing_native_exceptions": r"""
await installAbortHook();const sentinel=Error('native error');
class NativeXHR {
 open(method){if(method==='THROW')throw sentinel;return 1}
 send(){if(this.throwSend)throw sentinel;this.abort();return 2}
 abort(){return 3}
}
const realm={XMLHttpRequest:NativeXHR,URL,location:{href:'http://fixture/operator'},
 performance:{timeOrigin:1000,now:()=>10},
 [page.abortBindingName]:(value)=>Promise.resolve(page.abortBinding({page},value))};
runInNewContext('('+page.abortInit.toString()+')(arg)',{...realm,arg:page.abortInitArg});
const xhr=new NativeXHR();assert.equal(xhr.open('GET','/api/status'),1);
assert.equal(xhr.send(),2);await tick();
assert.equal(rows.filter(row=>row.file==='client-aborts.jsonl').length,1);
assert.throws(()=>xhr.open('THROW','/api/status'),error=>error===sentinel);
xhr.throwSend=true;assert.throws(()=>xhr.send(),error=>error===sentinel);
assert.equal(rows.filter(row=>row.file==='client-aborts.jsonl').length,1);
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
