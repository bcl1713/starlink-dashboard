import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import {
  stopExperimentServer,
  downloadAfterClick,
} from './bloom-lifecycle.mjs';

for (const ignoreTerm of [false, true])
  test(`reaps owned server after ${ignoreTerm ? 'forced' : 'signal'} termination`, async () => {
    const child = spawn(
      process.execPath,
      [
        '-e',
        `${ignoreTerm ? "process.on('SIGTERM',()=>{});" : ''}process.stdout.write('ready');setInterval(()=>{},1000);`,
      ],
      { detached: true, stdio: ['ignore', 'pipe', 'pipe'] }
    );
    try {
      await once(child.stdout, 'data');
      await stopExperimentServer(child, 30);
      assert.equal(child.signalCode, ignoreTerm ? 'SIGKILL' : 'SIGTERM');
      assert.throws(() => process.kill(child.pid, 0), { code: 'ESRCH' });
    } finally {
      if (child.exitCode === null && child.signalCode === null)
        process.kill(-child.pid, 'SIGKILL');
    }
  });
test('download cancellation is handled immediately while click is still pending', async () => {
  await assert.rejects(
    downloadAfterClick(
      () =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('download cancelled')), 5)
        ),
      () =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('click cancelled')), 50)
        )
    ),
    /download cancelled/
  );
  // Node's test runner reports any unhandled rejection after this point.
  await new Promise((resolve) => setTimeout(resolve, 60));
});
