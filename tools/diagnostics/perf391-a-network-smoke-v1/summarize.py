"""Describe retained partial evidence without certifying failed or absent streams."""
import collections, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
E=HERE/'evidence';R=E/'runtime';N=R/'browser/node'
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(line) for line in p.read_text().splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
raw=rows(N/'records.jsonl'); host=rows(R/'host.jsonl')
summary=read(N/'summary.json')
for relative,digest in summary['artifacts'].items():assert sha(N/relative)==digest
for relative,digest in read(N/'SHA256SUMS.json').items():
 # frozen collector uses a file map
 if isinstance(digest,str) and (N/relative).is_file():assert sha(N/relative)==digest
wakes=[r for r in raw if r.get('event',{}).get('phase')=='observer.wake']
gaps=[int(b['event']['mono_ns'])-int(a['event']['mono_ns']) for a,b in zip(wakes,wakes[1:])]
joins=[]
for request in [r for r in raw if r.get('phase')=='browser.request']:
 rid=request['requestId']; selected=[]
 for line,r in enumerate(raw,1):
  ev=r.get('event',{})
  if r.get('requestId')==rid or ev.get('op')==rid:
   selected.append({'line':line,'record':r})
 joins.append({'request_id':rid,'request_token':request.get('requestToken'),'state':'partial; no backend export or actual plot.commit snapshot','records':selected})
write(E/'actual-event-joins.json',{'input':'runtime/browser/node/records.jsonl','sha256':sha(N/'records.jsonl'),'joins':joins,'backend_join':'unavailable: backend stream was not exported after browser failure','complete_history_projection_actual_uplot_chain':False})
source=[r for r in raw if r.get('origin')=='source-body']
write(E/'observations-and-clocks.json',{'source_wakes':wakes,'source_gap_ns':gaps,'requirement_ns':1500000000,'cadence_pass':len(wakes)==5 and all(0<n<=1500000000 for n in gaps),'source_summary':summary['sources'],'source_response_artifacts':source,'host_rows':host,'node_clock':summary['host_identity'],'browser_clock_ids':sorted({r['event']['clock'] for r in raw if 'clock' in r.get('event',{})}),'durations':'source cadence uses only the Node monotonic domain; no cross-clock subtraction','readiness':'runtime/frontend-readiness.json includes host UTC and monotonic brackets'})
phases=collections.Counter(r.get('phase') or r.get('event',{}).get('phase') or r.get('origin','unknown') for r in raw)
snapshots=[r for r in raw if r.get('snapshots')]
report={'status':'FAIL_BROWSER_FINALIZATION_STOP','A_invocations':1,'C_invocations':0,'executor_exit':read(E/'execution-exit.json'),'runtime_result':read(R/'runtime-result.json'),'browser_failure':read(R/'browser/failure.json'),'frontend_readiness':read(R/'frontend-readiness.json'),'source_observations':len(source),'source_cadence_pass':len(wakes)==5 and all(0<n<=1500000000 for n in gaps),'host_summary':[r for r in host if r['kind']=='summary'],'browser_collection':summary,'frontend_final_summary':'unavailable; frontend-final.json absent','backend_stream_and_final_drop_summary':'unavailable; browser failure preceded backend drain/export','phase_counts':dict(phases),'actual_plot_commit_records':phases['plot.commit'],'retained_projection_plot_snapshot_records':len(snapshots),'screenshot_attempts':phases['paint.artifact'],'screenshot':read(R/'browser/compositor-result.json'),'visible_chart':'browser owner found a mounted, nonhidden committed panel o6; screenshot unavailable, no pixel proof','chart_chain':'incomplete: raw retained/history and plot.upload create/setData associations exist, but actual plot.commit and retained/projection/plot snapshots were not retained','zero_loss_gate':False,'cleanup':read(E/'final-host-cleanup.json')['clean'],'complete_smoke_pass':False,'historical_process_tests':'both timed out at 120s; not passing; no reruns','no_retry':True,'stop':'checkpoint review on draft PR #408'}
assert report['screenshot_attempts']==1
assert report['runtime_result']['failure']=='RuntimeError: browser smoke failure'
assert report['browser_failure']['reason']=='frontend final summary absent or changed'
assert not report['complete_smoke_pass'] and report['cleanup']
write(E/'outcome.json',report)
print(json.dumps({k:report[k] for k in ('status','source_observations','source_cadence_pass','host_summary','actual_plot_commit_records','screenshot_attempts','cleanup')},indent=2))
