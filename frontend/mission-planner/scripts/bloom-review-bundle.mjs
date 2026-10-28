import { execFileSync } from 'node:child_process';
import {
  cpSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  readdirSync,
} from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const repo = fileURLToPath(new URL('../../../', import.meta.url));
const sha = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: frontend,
  encoding: 'utf8',
}).trim();
const evidence = resolve(
  frontend,
  process.env.BLOOM_EVIDENCE ?? `test-results/bloom/${sha}`
);
const smoke = JSON.parse(readFileSync(resolve(evidence, 'smoke.json'), 'utf8'));
assert.equal(smoke.sha, sha);
assert.equal(smoke.buildStamp.sourceSha, sha);
assert.equal(smoke.buildStamp.dirty, false);
assert.equal(smoke.failure, undefined);
const cleanup = JSON.parse(
  readFileSync(resolve(evidence, 'cleanup.json'), 'utf8')
);
assert.equal(cleanup.result, 'clean');
const packageDir = resolve(frontend, `bloom-offline/${sha}`);
const stamp = JSON.parse(
  readFileSync(resolve(packageDir, 'dist-bloom/build.json'), 'utf8')
);
assert.equal(stamp.sourceSha, sha);
assert.equal(stamp.dirty, false);
assert.ok(
  readFileSync(resolve(evidence, 'A-default.png')).equals(
    readFileSync(resolve(evidence, 'A-restored.png'))
  ),
  'A must restore identically'
);
mkdirSync(resolve(packageDir, 'EVIDENCE'), { recursive: true });
for (const name of readdirSync(evidence).filter((name) =>
  /\.(png|json|csv)$/.test(name)
))
  cpSync(resolve(evidence, name), resolve(packageDir, 'EVIDENCE', name));
writeFileSync(
  resolve(packageDir, 'EVIDENCE/README.txt'),
  `Source: ${sha}\nClean copied-package smoke with explicit SwiftShader and external browser requests denied.\nA/output/B PNGs use the same paused camera and workload; visual-settings.json records settings.\nsmoke.json records real pointer picking regression results. Diagnostic timing is software-renderer smoke, NOT physical-laptop performance.\nOwner appearance, actual offline laptop launch and responsiveness acceptance remain pending.\n`
);
const directory = resolve(repo, '.bloom-work');
mkdirSync(directory, { recursive: true });
const archive = resolve(directory, `overview-bloom-${sha}.zip`);
execFileSync('python3', [
  '-c',
  "import sys,zipfile,pathlib; src=pathlib.Path(sys.argv[1]); z=zipfile.ZipFile(sys.argv[2],'w',zipfile.ZIP_DEFLATED); [z.write(p,pathlib.Path('overview-bloom')/p.relative_to(src)) for p in sorted(src.rglob('*')) if p.is_file()]; z.close(); z=zipfile.ZipFile(sys.argv[2]); assert z.testzip() is None",
  packageDir,
  archive,
]);
const digest = createHash('sha256').update(readFileSync(archive)).digest('hex');
writeFileSync(`${archive}.sha256`, `${digest}  overview-bloom-${sha}.zip\n`);
console.log(
  JSON.stringify({ sha, archive, sha256: digest, evidence }, null, 2)
);
