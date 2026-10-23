// Extract exact emitted diagnostic declarations for the existing probe fixtures.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const parser = require('/tmp/perf391-corrected-forge/builder/node_modules/@babel/parser');
const here = __dirname;
const root = path.join(here, 'evidence/A-assets');
const closure = JSON.parse(fs.readFileSync(path.join(root, 'perf391-module-closure.json')));
const chunk = Object.entries(closure.modules).find(([, rows]) => rows.some(m => m.id === 'diagnostic/browser-probe.ts' && m.renderedLength > 0))[0];
const bytes = fs.readFileSync(path.join(root, chunk));
const code = bytes.toString();
const ast = parser.parse(code, {sourceType: 'module'});
const body = ast.program.body;
const text = n => code.slice(n.start, n.end);
const functions = body.filter(n => n.type === 'FunctionDeclaration');
const snapshot = functions.find(n => text(n).includes('snapshot traversal cap'));
const probe = functions.find(n => text(n).includes('synthetic run/page token required'));
const attach = functions.find(n => text(n).includes('__perf391Host'));
const declarations = body.filter(n => n.type === 'VariableDeclaration').flatMap(n => n.declarations);
const limits = declarations.find(n => text(n).includes('Object.freeze({events:256,'));
const hostName = text(attach).match(/(\w+)\.__perf391Host/)[1];
const host = declarations.find(n => n.id.name === hostName);
const diagnostic = declarations.find(n => n.init?.type === 'CallExpression' && n.init.callee.name === attach.id.name);
const readCommit = body.find(n => n.type === 'ExpressionStatement' && text(n).includes('__perf391ReadCommit='));
const finish = body.find(n => n.type === 'ExpressionStatement' && text(n).startsWith('globalThis.__perf391Finish='));
for (const node of [snapshot,probe,attach,limits,host,diagnostic,readCommit,finish]) if (!node) throw Error('compiled diagnostic declaration absent');
if (!text(snapshot).includes('encode(JSON.stringify(')) throw Error('exact encoded-byte accounting absent');
for(const phase of ['plot.commit','react.commit','query.error']) if(!text(probe).includes(phase)) throw Error('compiled phase absent '+phase);
if (!text(finish).includes('frontend not drained')) throw Error('Finish attribution absent');
const shim = [
  'const '+text(limits)+';', text(snapshot), text(probe), 'const '+text(host)+';',
  text(attach), 'const '+text(diagnostic)+';', text(readCommit), text(finish),
  `export {${probe.id.name} as createProbe, ${limits.id.name} as LIMITS, ${diagnostic.id.name} as diagnostic};`,
].join('\n');
const output = '/tmp/perf391-corrected-forge/compiled-probe.mjs';
fs.writeFileSync(output,shim);
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
fs.writeFileSync(path.join(here,'evidence/compiled-extraction.json'),JSON.stringify({
  chunk,chunk_sha256:hash(bytes), compiled_fixture_module_sha256:hash(shim),
  method:'AST slices from emitted image chunk; declaration bytes unchanged; export names added for existing fixtures',
  declarations:[snapshot,probe,attach,limits,host,diagnostic,readCommit,finish].map(n=>({type:n.type,start:n.start,end:n.end,sha256:hash(text(n))})),
  exact_json_byte_accounting:true, compiled_plot_and_react_commit:true, compiled_query_failure:true, compiled_finish_guard:true,
},null,2)+'\n');
console.log('Extracted exact compiled probe/commit/Finish declarations from '+chunk);
const assert = require('node:assert/strict');
const createProbe = new Function('const '+text(limits)+';'+text(snapshot)+text(probe)+';return '+probe.id.name)();
const makeFinish = new Function(diagnostic.id.name, text(finish)+';return globalThis.__perf391Finish;');
assert.throws(()=>makeFinish(undefined)(),/diagnostic handshake absent/);
for(const key of ['pending','inflight','failed','lost']) {
  const summary={pending:0,inflight:0,failed:false,lost:0,[key]:1};
  assert.throws(()=>makeFinish({summary:()=>summary})(),/frontend not drained/);
}
const healthy=createProbe({run:'synthetic-compiled',page:'p1',document:'d1',clock:()=>1,binding:async()=>true});
const finished=makeFinish(healthy)();
assert.equal(finished.before.closed,false);
assert.equal(finished.after.closed,true);
assert.equal(finished.after.lost,0);
console.log('Exact compiled Finish: absent handshake, four failure/drain guards, and successful close verified.');
