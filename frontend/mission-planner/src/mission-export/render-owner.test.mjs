import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
export function registerOwnerTests({ run, clean, root, assetRoot }) {
  test('SIGTERM closes contexts and reaps browser', async () => {
    assert.ok(
      existsSync(new URL('./briefing-render.mjs', import.meta.url)),
      'combined renderer contract absent'
    );
    const out = path.join(root, 'runtime', 'signal');
    await mkdir(out, { recursive: true });
    const child = spawn(
      process.execPath,
      [
        'src/mission-export/briefing-render.mjs',
        path.join(root, 'inputs', 'composition-assessed.json'),
        out,
        assetRoot,
      ],
      {
        env: {
          ...process.env,
          CHECKPOINT_FAULT: 'map-hang',
          CHECKPOINT_BUDGET_MS: '12000',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    );
    const exit = new Promise((resolve) =>
      child.once('exit', (code, signal) => resolve({ code, signal }))
    );
    let stderr = '';
    child.stderr.on('data', (b) => (stderr += b));
    child.stdout.resume();
    const deadline = Date.now() + 10000;
    let owned;
    try {
      while (Date.now() < deadline) {
        try {
          owned = JSON.parse(
            await readFile(path.join(out, 'ownership.json'), 'utf8')
          );
          if (owned.browserPid) break;
        } catch {}
        await new Promise((r) => setTimeout(r, 30));
      }
      assert.ok(owned?.browserPid, stderr);
      child.kill('SIGTERM');
      const result = await exit;
      assert.equal(result.code, 1, stderr);
      const report = JSON.parse(
        await readFile(path.join(out, 'render-report.json'), 'utf8')
      );
      assert.equal(report.errorCode, 'cancelled');
      clean(report);
    } finally {
      if (child.exitCode === null && child.signalCode === null) {
        child.kill('SIGTERM');
        await exit;
      }
    }
  });
}
