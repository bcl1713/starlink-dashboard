"""Separate diagnosis; never alter or qualify the failed native run."""
import hashlib,json,subprocess,sys
from pathlib import Path
S=Path(__file__).resolve().parent;R=S/'sustained-001';W=Path('/home/oracle-worker/Work/starlink-dashboard/.worktrees/issue-393-clean-soak');D=S/'sustained-001-diagnosis';D.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
raw=R/'api-outcomes.jsonl';before=sha(raw);kept=[];excluded=[]
for line in raw.read_text().splitlines(keepends=True):
 v=json.loads(line)
 if v.get('startedPhase')=='teardown':excluded.append(v)
 else:kept.append(line)
filtered=D/'pre-teardown-api-outcomes.jsonl';filtered.write_text(''.join(kept))
args={'apiPath':str(filtered),'abortPath':str(R/'client-aborts.jsonl'),'transitionPath':str(R/'coordination.jsonl')}
program="const{qualifyCancellations}=await import(process.argv[1]);console.log(JSON.stringify(await qualifyCancellations(JSON.parse(process.argv[2])),null,2));"
x=subprocess.run([str(S/'node-v22.22.2-linux-x64/bin/node'),'--input-type=module','--eval',program,(W/'tools/acceptance/performance/cancellations.mjs').as_uri(),json.dumps(args)],capture_output=True,text=True,check=True,timeout=30)
(D/'derived-cancellation-proof.json').write_text(x.stdout);proof=json.loads(x.stdout)
assert proof['clean'] and proof['counts']['measured_cancellations']==1 and proof['counts']['expected']==1 and proof['counts']['unexpected']==0,proof
assert sha(raw)==before
meta={'native_status':'failed','native_qualification_clean':False,'native_polling_gate_passed':False,'sustained_qualification_claim':False,'purpose':'Classify the one measured cancellation independently after the unchanged native polling failure. Does not repair, qualify or replace the native run.','raw_api_sha256':before,'derived_api_sha256':sha(filtered),'filter':'Exclude only rows with startedPhase == teardown; preserve every warmup/measured row byte-for-byte. The failure cleanup had two incomplete teardown requests; they remain in raw evidence.','excluded_teardown_rows':len(excluded),'excluded_teardown_starts':sum(x['event']=='start' for x in excluded),'excluded_teardown_terminals':sum(x['event']=='terminal' for x in excluded),'classifier_harness_sha':'ca551a0e94b93bbcd0b45b2a69567354f5094098','classifier_source_sha256':proof['source_sha256'],'derived_counts':proof['counts'],'raw_cancellation_cause':'unknown','derived_cancellation_outcome':'Observed XHR abort in declared reactivation window with matching CDP timing and successful bounded new-source recovery; not an observed internal reason.'}
(D/'derivation.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
