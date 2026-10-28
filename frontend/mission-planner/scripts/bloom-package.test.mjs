import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  cpSync,
  readFileSync,
  rmSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';

test('offline packaging refuses dirty sources and a stale build; ships its run sheet', () => {
  const dir = mkdtempSync(join(tmpdir(), 'issue429-package-test-'));
  try {
    const frontend = join(dir, 'frontend/mission-planner');
    mkdirSync(join(frontend, 'scripts'), { recursive: true });
    mkdirSync(join(frontend, 'dist-bloom'), { recursive: true });
    mkdirSync(join(dir, 'docs/development'), { recursive: true });
    cpSync(
      new URL('./bloom-package.mjs', import.meta.url),
      join(frontend, 'scripts/bloom-package.mjs')
    );
    writeFileSync(join(frontend, 'scripts/bloom-server.mjs'), '// server v1');
    writeFileSync(
      join(dir, 'docs/development/overview-bloom-experiment.md'),
      '# Offline run sheet'
    );
    writeFileSync(
      join(dir, '.gitignore'),
      'frontend/mission-planner/dist-bloom/\nfrontend/mission-planner/bloom-offline/\n'
    );
    const git = (...args) =>
      execFileSync('git', args, { cwd: dir, encoding: 'utf8' }).trim();
    git('init', '-q');
    git('add', '.');
    git(
      '-c',
      'user.name=Experiment Test',
      '-c',
      'user.email=test@example.invalid',
      'commit',
      '-qm',
      'fixture'
    );
    const sha = git('rev-parse', 'HEAD');
    writeFileSync(
      join(frontend, 'dist-bloom/build.json'),
      JSON.stringify({ sourceSha: sha, dirty: false })
    );
    writeFileSync(
      join(frontend, 'scripts/bloom-server.mjs'),
      '// dirty server'
    );
    const run = () =>
      spawnSync(process.execPath, ['scripts/bloom-package.mjs'], {
        cwd: frontend,
        encoding: 'utf8',
      });
    assert.notEqual(run().status, 0, 'dirty source must be refused');
    git('checkout', '--', 'frontend/mission-planner/scripts/bloom-server.mjs');
    assert.equal(run().status, 0, 'matching clean build must package');
    assert.equal(
      readFileSync(
        join(frontend, 'bloom-offline', sha, 'RUN-SHEET.md'),
        'utf8'
      ),
      '# Offline run sheet'
    );
    git(
      '-c',
      'user.name=Experiment Test',
      '-c',
      'user.email=test@example.invalid',
      'commit',
      '--allow-empty',
      '-qm',
      'new head'
    );
    assert.notEqual(run().status, 0, 'build from an older SHA must be refused');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
