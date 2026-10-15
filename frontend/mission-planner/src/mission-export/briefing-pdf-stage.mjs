import { spawn } from 'node:child_process';
import { writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { within } from './render-budget.mjs';
import { ownedPath } from './render-owner.mjs';
const pdfError = (message) =>
  Object.assign(new Error(message), { code: 'pdf' });

/** Inspect actual PDF cells within the caller's remaining work allowance. */
export async function verifyPdfInOwner(
  { owner, budget, pdfPath, expectations, fault },
  dependencies = {}
) {
  const expectedPath = ownedPath(owner.outputRoot, 'pdf-expectations.json');
  await writeFile(expectedPath, JSON.stringify(expectations));
  const allowance = budget.workRemainingMs();
  const args =
    dependencies.command?.() ??
    (fault === 'verify-hang'
      ? [
          process.env.BRIEFING_PYTHON || 'python3',
          '-c',
          'import time; time.sleep(3600)',
        ]
      : [
          process.env.BRIEFING_PYTHON || 'python3',
          '-m',
          'app.mission.exporter.customer_pdf',
          path.resolve(pdfPath),
          expectedPath,
          '--timeout-seconds',
          String(allowance / 1000),
        ]);
  let child, release, completion;
  try {
    child = spawn(args[0], args.slice(1), {
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '',
      stderr = '';
    child.stdout.on('data', (data) => {
      stdout += data;
      if (stdout.length > 8_000_000) child.kill('SIGTERM');
    });
    child.stderr.on('data', (data) => {
      stderr = (stderr + data).slice(-4000);
    });
    completion = new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('close', (code) => resolve(code));
    });
    release = await owner.trackChild(child, args);
    const code = await within(completion, budget.workRemainingMs());
    if (code !== 0) throw pdfError('PDF verification failed: ' + stderr);
    let result;
    try {
      result = JSON.parse(stdout);
    } catch {
      throw pdfError('Invalid PDF verification response');
    }
    if (result.verified !== true) throw pdfError('PDF rows not verified');
    budget.workRemainingMs();
    return result;
  } finally {
    if (child && child.exitCode === null && child.signalCode === null) {
      try {
        process.kill(-child.pid, 'SIGTERM');
      } catch {}
      let remaining = 1;
      try {
        remaining = Math.min(250, budget.remainingMs());
      } catch {}
      try {
        await within(completion, remaining);
      } catch {
        try {
          process.kill(-child.pid, 'SIGKILL');
        } catch {}
        await completion.catch(() => {});
      }
    }
    await release?.();
    await rm(expectedPath, { force: true });
  }
}
