import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
const root = new URL('../', import.meta.url);
const stamp = JSON.parse(
  await readFile(new URL('dist-bloom/build.json', root), 'utf8')
);
const head = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: root,
  encoding: 'utf8',
}).trim();
const dirty = execFileSync('git', ['status', '--porcelain'], {
  cwd: root,
  encoding: 'utf8',
}).trim();
if (stamp.dirty || dirty || head !== stamp.sourceSha)
  throw new Error(
    'Commit the experiment sources and rebuild before packaging.'
  );
const output = new URL(`bloom-offline/${stamp.sourceSha}/`, root);
await mkdir(new URL('scripts/', output), { recursive: true });
await cp(new URL('dist-bloom/', root), new URL('dist-bloom/', output), {
  recursive: true,
});
await cp(
  new URL('scripts/bloom-server.mjs', root),
  new URL('scripts/bloom-server.mjs', output)
);
await cp(
  new URL('../../docs/development/overview-bloom-experiment.md', root),
  new URL('RUN-SHEET.md', output)
);
await writeFile(
  new URL('START.txt', output),
  `Synthetic offline Overview bloom experiment\nSource SHA: ${stamp.sourceSha}\n\nRequires Node ^22.22.2 installed before going offline. No npm install or backend is needed.\nStart from this folder: node scripts/bloom-server.mjs\nOpen http://127.0.0.1:4290 in a fresh browser profile. Stop: Ctrl+C.\n\nA is current/default. B is real bloom. Do not use operational records or production origins.\nRead RUN-SHEET.md for comparisons, limitations and cleanup. This specimen is not the complete operational stack.\n`
);
console.log(fileURLToPath(output));
