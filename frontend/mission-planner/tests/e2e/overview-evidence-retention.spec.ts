import { expect, test } from '@playwright/test';
import {
  mkdtemp,
  mkdir,
  readFile,
  rm,
  stat,
  writeFile,
} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import {
  validateOverviewArtifactManifest,
  writeOverviewArtifact,
} from './support/overview-artifacts';
import { redactContinuityArtifact } from './support/overview-cdp-capture';

test.describe('Operations overview evidence retention', () => {
  test.describe.configure({ mode: 'serial' });

  let root = '';
  let previousEnvironment: Record<string, string | undefined>;

  test.beforeEach(async () => {
    root = await mkdtemp(path.join(os.tmpdir(), 'overview-evidence-'));
    const keys = [
      'OVERVIEW_ARTIFACT_DIR',
      'OVERVIEW_EVIDENCE_COMMIT_SHA',
      'OVERVIEW_EVIDENCE_BRANCH',
      'OVERVIEW_EVIDENCE_REF',
      'OVERVIEW_EVIDENCE_CLEAN_WORKTREE',
      'OVERVIEW_EVIDENCE_CAPTURE_STARTED_AT_UTC',
    ];
    previousEnvironment = Object.fromEntries(
      keys.map((key) => [key, process.env[key]])
    );
    Object.assign(process.env, {
      OVERVIEW_ARTIFACT_DIR: path.join(
        root,
        '0123456789012345678901234567890123456789',
        'task-13'
      ),
      OVERVIEW_EVIDENCE_COMMIT_SHA: '0123456789012345678901234567890123456789',
      OVERVIEW_EVIDENCE_BRANCH: 'fixture',
      OVERVIEW_EVIDENCE_REF: 'fixture',
      OVERVIEW_EVIDENCE_CLEAN_WORKTREE: 'true',
      OVERVIEW_EVIDENCE_CAPTURE_STARTED_AT_UTC: '2026-01-01T00:00:00.000Z',
    });
  });

  test.afterEach(async () => {
    for (const [key, value] of Object.entries(previousEnvironment)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    await rm(root, { recursive: true, force: true });
  });

  test('persists only redacted bounded continuity JSON and its verified manifest', async () => {
    const artifact = redactContinuityArtifact({
      captureMetadata: { source: 'fixture' },
      frames: [],
      eventLedger: {
        installedAt: 1,
        stoppedAt: 2,
        mutations: [],
        identityTransitions: [],
        retention: { status: 'complete', overflowed: [], retained: {} },
        samples: [
          {
            at: 1,
            phase: 'baseline',
            request: null,
            activeRequestIds: [],
            activeRequests: [],
            identities: {},
            regions: [
              {
                key: 'summary',
                identity: 'object-1',
                width: 1,
                height: 1,
                signature: 'DOM text must not be retained',
              },
            ],
            layers: [],
            charts: [],
            focusId: null,
            focusLabel: 'DOM text must not be retained',
            scrollX: 0,
            scrollY: 0,
            poiFilter: '',
            disclosures: [],
          },
        ],
      },
      cdpNetworkLedger: [],
      cdpNetworkEvents: [],
      cdpRetention: { status: 'complete', overflowed: [], retained: {} },
      fixtureRequestLedger: [
        {
          id: 'router-1',
          cycle: 1,
          event: 'complete',
          kind: 'scheduled',
          source: 'telemetry',
          method: 'GET',
          url: 'http://localhost/api/overview?secret=query-value',
          status: 200,
          outcome: 'finished',
          firstParty: true,
        },
      ],
      cycles: [],
    });
    const json = JSON.stringify(artifact, null, 2);

    await writeOverviewArtifact('event-continuity-fixture.json', json);
    await validateOverviewArtifactManifest();

    const retained = await readFile(
      path.join(
        process.env.OVERVIEW_ARTIFACT_DIR!,
        'event-continuity-fixture.json'
      ),
      'utf8'
    );
    expect(retained).not.toContain('secret=query-value');
    expect(retained).not.toContain('DOM text must not be retained');
    expect(retained).toContain('"url": "/api/overview"');
    expect(await stat(process.env.OVERVIEW_ARTIFACT_DIR!)).toMatchObject({
      mode: expect.any(Number),
    });
    expect((await stat(process.env.OVERVIEW_ARTIFACT_DIR!)).mode & 0o777).toBe(
      0o700
    );
    expect(
      (
        await stat(
          path.join(
            process.env.OVERVIEW_ARTIFACT_DIR!,
            'event-continuity-fixture.json'
          )
        )
      ).mode & 0o777
    ).toBe(0o600);
  });

  test('rejects insecure pre-existing directories and files', async () => {
    const insecureDirectory = process.env.OVERVIEW_ARTIFACT_DIR!;
    await mkdir(insecureDirectory, { recursive: true, mode: 0o755 });
    await expect(writeOverviewArtifact('unsafe.json', '{}')).rejects.toThrow(
      /insecure evidence directory/i
    );

    await rm(insecureDirectory, { recursive: true, force: true });
    await mkdir(insecureDirectory, { recursive: true, mode: 0o700 });
    await writeFile(path.join(insecureDirectory, 'unsafe.json'), '{}', {
      mode: 0o644,
    });
    await expect(writeOverviewArtifact('unsafe.json', '{}')).rejects.toThrow(
      /insecure evidence artifact/i
    );
  });

  test('rejects a manifest whose checksum inventory no longer matches evidence', async () => {
    await writeOverviewArtifact('bounded.json', '{"safe":true}');
    await writeFile(
      path.join(process.env.OVERVIEW_ARTIFACT_DIR!, 'bounded.json'),
      '{"safe":false}',
      { mode: 0o600 }
    );
    await expect(validateOverviewArtifactManifest()).rejects.toThrow(
      /checksum mismatch/i
    );
  });
});
