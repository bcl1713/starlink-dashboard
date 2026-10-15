import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
async function stage() {
  assert.ok(
    existsSync(new URL('./briefing-pdf-stage.mjs', import.meta.url)),
    'Bounded verifier contract absent'
  );
  return (await import('./briefing-pdf-stage.mjs')).verifyPdfInOwner;
}
async function run(script, remaining = 1000) {
  const root = await mkdtemp(path.join(tmpdir(), 'briefing-verifier-unit-'));
  let child,
    released = false;
  const owner = {
    outputRoot: root,
    trackChild: async (c) => {
      child = c;
      assert.ok(c.pid);
      return async () => {
        released = true;
      };
    },
  };
  const budget = { workRemainingMs: () => remaining, remainingMs: () => 1000 };
  try {
    return {
      result: await (
        await stage()
      )(
        {
          owner,
          budget,
          pdfPath: path.join(root, 'test.pdf'),
          expectations: {},
        },
        { command: () => [process.execPath, '-e', script] }
      ),
      child,
      released,
    };
  } catch (error) {
    error.child = child;
    error.released = released;
    throw error;
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}
test('verifier process registers ownership and reaps before returning proof', async () => {
  const r = await run('console.log(JSON.stringify({verified:true,rows:[]}))');
  assert.equal(r.result.verified, true);
  assert.ok(r.released);
  assert.equal(r.child.exitCode, 0);
});
test('hung verifier uses remaining shared time and reaps its owned process', async () => {
  await assert.rejects(
    run('setInterval(()=>{},1000)', 30),
    (e) =>
      e.code === 'deadline' &&
      e.released &&
      (e.child.signalCode !== null || e.child.exitCode !== null)
  );
});
test('invalid verifier output rejects evidence after reaping', async () => {
  await assert.rejects(
    run('console.log("not-json")'),
    (e) => e.code === 'pdf' && e.released && e.child.exitCode === 0
  );
});
