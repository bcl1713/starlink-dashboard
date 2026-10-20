import { expect, it } from 'vitest';
import { collectArchiveEvidence } from './trainingArchiveEvidence';
import {
  identity,
  namespace,
  records,
  zip,
  health,
  observation,
} from '@/test/training-archive-fixtures';
const read = (values: unknown, backend = records, H = 2) =>
  collectArchiveEvidence(identity, namespace, H, backend, values);
it('derives outcomes from selected bytes, ready artifact, checksums, source history and two import comparisons', () => {
  const one = observation('empty');
  expect(read([one])).toEqual(
    expect.arrayContaining([
      'export-downloaded',
      'archive-contents-validated',
      'export-cancel-recovery',
    ])
  );
  expect(read([one])).not.toContain('archive-imported-isolated');
  expect(read([one, observation('nonempty')])).toContain(
    'archive-imported-isolated'
  );
});
it('rejects foreign identities, changed ZIP bytes, future or contradictory source history and unchecked members', () => {
  const one = observation('empty');
  const changed = structuredClone(one);
  changed.report.inspection.checksumReads[0].actual = 'f'.repeat(64);
  const epoch = structuredClone(one);
  epoch.report.identity.epoch = 'foreign';
  for (const value of [
    [{ passed: true }],
    [{ ...one, zip: { ...zip, sha256: 'f'.repeat(64) } }],
    [changed],
    [epoch],
  ])
    expect(() => read(value)).toThrow();
  expect(() =>
    read([one], [records[0], { ...records[1], reason: 'contradictory' }])
  ).toThrow();
  expect(() => read([one], records, 1)).toThrow();
});
it('rejects changed destination journal, a shared store and an unrelated prior mission', () => {
  for (const mutate of [
    (v: ReturnType<typeof observation>) => {
      v.report.transfer.after.H = 5;
    },
    (v: ReturnType<typeof observation>) => {
      v.report.transfer.after.health = health;
    },
    (v: ReturnType<typeof observation>) => {
      v.report.importedMission.id = 'prior-import';
    },
  ]) {
    const one = structuredClone(observation('nonempty'));
    mutate(one);
    expect(() => read([one])).toThrow();
  }
});

it('keeps human PDF review and client network failure separate from cancellation recovery', () => {
  const one = observation('empty');
  expect(read([one])).not.toContain('pdf-extracted-reviewed');
  expect(read([one])).not.toContain('export-failure-observed');
  one.report.preparations[0].job.finished_at = 10;
  expect(read([one])).not.toContain('export-cancel-recovery');
});

it('requires a new installed file generation for a same-ID re-import and rejects an unchanged check', () => {
  const replacement = observation('nonempty');
  expect(read([observation('empty'), replacement])).toContain(
    'archive-imported-isolated'
  );
  replacement.report.transfer.after.planFiles =
    replacement.report.transfer.before.planFiles;
  expect(() => read([replacement])).toThrow();
});
