import { record } from '@/test/operator-fixtures';
export const identity = {
  origin: 'http://localhost:56533',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
export const namespace =
  'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const first = {
  ...record,
  provenance: { ...record.provenance, source_mode: 'simulation' as const },
};
const latest = {
  ...first,
  version: 2,
  previous_version: 1,
  journal_seq: 2,
  command_id: 'edited',
};
export const records = [first, latest];
export const zip = { name: 'original.zip', sha256: 'a'.repeat(64), size: 100 };
const legs = [
  { id: 'one', name: 'First leg', transports: { X: true } },
  { id: 'two', name: 'Second leg', transports: { X: true } },
];
export const health = {
  ready: true,
  store_id: 'store',
  api_epoch: 'epoch-a',
  source_mode: 'simulation',
  simulation_run_id: namespace,
};
const destination = {
  ...health,
  store_id: 'other-store',
  api_epoch: 'other-epoch',
  simulation_run_id: 'synthetic-import',
};
const checks = [
  'operations/journal.json',
  'operations/audit.jsonl',
  'operations/current.json',
  'operations/manifest.json',
  'operations/activity.jsonl',
  'operations/events.json',
  'operations/handover.txt',
  'telemetry/manifest.json',
  ...['001', '002'].flatMap((id) =>
    ['manifest.json', 'observations.csv', 'events.csv'].map(
      (file) => `telemetry/legs/${id}/${file}`
    )
  ),
].map((path) => ({ path, expected: 'b'.repeat(64), actual: 'b'.repeat(64) }));
export function observation(label: 'empty' | 'nonempty') {
  const sentinel = { ...first, record_id: 'destination-note' };
  const planFile = {
    mission_id: `import-${label}`,
    device: '1',
    inode: '10',
    modifiedNs: '100',
    sha256: 'd'.repeat(64),
    size: 100,
  };
  const before = {
    health: destination,
    H: label === 'empty' ? 0 : 1,
    records: label === 'empty' ? [] : [sentinel],
    history: label === 'empty' ? [] : [sentinel],
    missions: label === 'empty' ? [] : [{ id: `import-${label}` }],
    planFiles: label === 'empty' ? [] : [planFile],
  };
  const after = {
    ...before,
    missions: label === 'empty' ? [{ id: `import-${label}` }] : before.missions,
    planFiles: [{ ...planFile, inode: '11', modifiedNs: '101' }],
  };
  return {
    zip,
    report: {
      schemaVersion: 1,
      kind: 'operator-training-archive-evidence',
      identity,
      namespace,
      label,
      source: {
        health,
        H: 2,
        records: [latest],
        history: records,
        mission: { id: identity.missionId, legs },
      },
      inspection: {
        synthetic: true,
        zipSha256: zip.sha256,
        pdfPath: 'exports/mission/original-brief.pdf',
        pdfSha256: 'd'.repeat(64),
        pdfPages: 2,
        records: 1,
        revisions: 2,
        checksumReads: checks,
        telemetry: ['001', '002'].map((id) => ({
          path: `legs/${id}`,
          state: 'sealed',
          events: ['off_blocks', 'takeoff', 'landed', 'on_blocks'],
        })),
        telemetryInputProvenance: {
          synthetic: true,
          source_format: 'synthetic-operational-format',
        },
      },
      preparations: [
        {
          job: {
            id: '1'.repeat(32),
            mission_id: identity.missionId,
            state: 'cancelled',
            fingerprint: 'c'.repeat(64),
            queued_at: 1,
            finished_at: 2,
          },
        },
        {
          job: {
            id: '2'.repeat(32),
            mission_id: identity.missionId,
            state: 'ready',
            fingerprint: 'c'.repeat(64),
            queued_at: 3,
            finished_at: 4,
            briefing_status: 'included',
          },
          artifact: { sha256: zip.sha256, size: zip.size },
        },
      ],
      transfer: { before, after },
      importedMission: { id: `import-${label}`, legs },
    },
  };
}
