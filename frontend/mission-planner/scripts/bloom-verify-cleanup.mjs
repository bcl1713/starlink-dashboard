import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const sha = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: root,
  encoding: 'utf8',
}).trim();
const evidence = resolve(
  root,
  process.env.BLOOM_EVIDENCE ?? `test-results/bloom/${sha}`
);
const owner = JSON.parse(
  readFileSync(resolve(evidence, 'ownership.json'), 'utf8')
);
const pids = [owner.server?.pid, owner.browser?.pid].filter(Boolean);
const groups = [owner.server?.pgid, owner.browser?.pgid].filter(Boolean);
const survivors = execFileSync('ps', ['-eo', 'pid=,pgid=,args='], {
  encoding: 'utf8',
})
  .split('\n')
  .filter((row) => {
    const [pid, group] = row.trim().split(/\s+/, 2).map(Number);
    return pids.includes(pid) || groups.includes(group);
  });
const port = new URL(owner.server?.origin ?? 'http://127.0.0.1:4290').port;
const listeners = execFileSync('ss', ['-H', '-ltnp'], { encoding: 'utf8' })
  .split('\n')
  .filter((row) => row.trim().split(/\s+/)[3]?.endsWith(`:${port}`));
const report = {
  sha,
  pids,
  groups,
  survivors,
  listeners,
  composeProjects: [],
  privateVolumes: [],
  result: survivors.length || listeners.length ? 'failed' : 'clean',
};
writeFileSync(
  resolve(evidence, 'cleanup.json'),
  JSON.stringify(report, null, 2)
);
assert.deepEqual(survivors, [], 'owned process/group still alive');
assert.deepEqual(listeners, [], 'experiment port still listening');
console.log('Owned experiment processes, groups and listeners are gone.');
