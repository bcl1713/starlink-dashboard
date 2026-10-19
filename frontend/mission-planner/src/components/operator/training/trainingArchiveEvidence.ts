import { z } from 'zod';
import type { SavedRecord } from '@/types/operator';
import type { TrainingIdentity } from './trainingProgress';
import { sameJson } from './trainingRecordIdentity';

const hash = z.string().regex(/^[a-f0-9]{64}$/);
const text = z.string().min(1);
const integer = z.number().int().nonnegative();
const identitySchema = z.object({
  origin: text,
  fixtureVersion: z.literal(1),
  storeId: text,
  epoch: text,
  missionId: text,
});
const healthSchema = z
  .object({
    ready: z.literal(true),
    store_id: text,
    api_epoch: text,
    source_mode: z.literal('simulation'),
    simulation_run_id: text,
    clock_regression: z.literal(false).optional(),
  })
  .passthrough();
const saved = z.custom<SavedRecord>((value) => {
  const r = value as SavedRecord | null;
  return (
    !!r &&
    typeof r === 'object' &&
    typeof r.record_id === 'string' &&
    !!r.record_id &&
    typeof r.mission_id === 'string' &&
    typeof r.command_id === 'string' &&
    Number.isInteger(r.version) &&
    r.version > 0 &&
    Number.isInteger(r.journal_seq) &&
    r.journal_seq > 0 &&
    r.provenance?.source_mode === 'simulation'
  );
}, 'Raw saved revisions required');
const rows = z.array(saved).max(10000);
const missionSchema = z
  .object({
    id: text,
    legs: z
      .array(
        z
          .object({ id: text, name: text, transports: z.unknown() })
          .passthrough()
      )
      .length(2),
  })
  .passthrough();
const destinationSchema = z.object({
  health: healthSchema,
  H: integer,
  records: rows,
  history: rows,
  missions: z.array(z.object({ id: text }).passthrough()).max(1000),
});
const jobSchema = z
  .object({
    id: z.string().regex(/^[a-f0-9]{32}$/),
    mission_id: text,
    state: z.enum([
      'queued',
      'preparing',
      'ready',
      'failed',
      'cancelled',
      'superseded',
      'expired',
    ]),
    fingerprint: hash,
    queued_at: z.number().finite(),
    finished_at: z.number().finite().nullable(),
    briefing_status: z.string().nullable().optional(),
  })
  .passthrough();
const reportSchema = z.object({
  schemaVersion: z.literal(1),
  kind: z.literal('operator-training-archive-evidence'),
  identity: identitySchema,
  namespace: z.string().regex(/^operator-training-v1-[0-9a-f-]{36}$/),
  label: z.enum(['empty', 'nonempty']),
  source: z.object({
    health: healthSchema,
    H: integer,
    records: rows,
    history: rows,
    mission: missionSchema,
  }),
  inspection: z
    .object({
      synthetic: z.literal(true),
      zipSha256: hash,
      pdfPath: text,
      pdfSha256: hash,
      pdfPages: z.number().int().min(2),
      records: integer,
      revisions: integer,
      checksumReads: z
        .array(z.object({ path: text, expected: hash, actual: hash }))
        .min(1)
        .max(1000),
      telemetry: z
        .array(
          z.object({
            path: text,
            state: z.literal('sealed'),
            events: z.array(text).max(100),
          })
        )
        .length(2),
      telemetryInputProvenance: z
        .object({
          synthetic: z.literal(true),
          source_format: z.literal('synthetic-operational-format'),
        })
        .passthrough(),
    })
    .passthrough(),
  preparations: z
    .array(
      z.object({
        job: jobSchema,
        artifact: z.object({ sha256: hash, size: integer }).optional(),
      })
    )
    .max(100),
  transfer: z.object({ before: destinationSchema, after: destinationSchema }),
  importedMission: missionSchema,
});
const observationSchema = z.object({
  report: reportSchema,
  zip: z.object({
    name: text,
    sha256: hash,
    size: z
      .number()
      .int()
      .positive()
      .max(64 * 1024 * 1024),
  }),
});
export type ArchiveObservation = z.infer<typeof observationSchema>;

export function decodeArchiveObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): ArchiveObservation {
  const parsed = observationSchema.safeParse(value);
  if (!parsed.success)
    throw new Error(
      'Private archive evidence is incomplete or has an invalid schema. Regenerate it with the private check command.'
    );
  const observation = parsed.data;
  const r = observation.report,
    health = r.source.health;
  if (
    !sameJson(r.identity, identity) ||
    (namespace !== undefined && r.namespace !== namespace) ||
    health.store_id !== identity.storeId ||
    health.api_epoch !== identity.epoch ||
    health.simulation_run_id !== r.namespace ||
    r.source.mission.id !== identity.missionId
  )
    throw new Error(
      'Archive evidence belongs to another private source identity'
    );
  return observation;
}
function equalRows(a: readonly SavedRecord[], b: readonly SavedRecord[]) {
  const order = (rows: readonly SavedRecord[]) =>
    [...rows].sort(
      (a, b) => a.record_id.localeCompare(b.record_id) || a.version - b.version
    );
  return (
    new Set(a.map((r) => `${r.record_id}:${r.version}`)).size === a.length &&
    new Set(b.map((r) => `${r.record_id}:${r.version}`)).size === b.length &&
    sameJson(order(a), order(b))
  );
}
function actualBoundary(
  records: readonly SavedRecord[],
  missionId: string,
  H: number
) {
  const versions = new Map<string, SavedRecord>();
  for (const row of records) {
    if (row.mission_id !== missionId || row.journal_seq > H) continue;
    const key = `${row.record_id}:${row.version}`,
      prior = versions.get(key);
    if (prior && !sameJson(prior, row))
      throw new Error('Backend history contradicts an archived revision');
    versions.set(key, row);
  }
  const current = new Map<string, SavedRecord>();
  for (const row of versions.values())
    if ((current.get(row.record_id)?.version ?? 0) < row.version)
      current.set(row.record_id, row);
  return { current: [...current.values()], history: [...versions.values()] };
}
/** Imported tool facts are distinct from current backend reads and human observations. */
export function collectArchiveEvidence(
  identity: TrainingIdentity,
  namespace: string,
  H: number | undefined,
  backend: readonly SavedRecord[],
  values: unknown
): string[] {
  if (values === undefined) return [];
  if (
    !Array.isArray(values) ||
    values.length > 2 ||
    !Number.isInteger(H) ||
    H === undefined ||
    H < 0
  )
    throw new Error(
      'Bounded archive observations and a current journal boundary required'
    );
  const observations = values.map((value) =>
    decodeArchiveObservation(value, identity, namespace)
  );
  if (
    new Set(observations.map((item) => item.report.label)).size !==
    observations.length
  )
    throw new Error('Use distinct empty and nonempty import observations');
  const outcomes = new Set<string>();
  let digest: string | undefined;
  for (const { report: r, zip } of observations) {
    if (r.source.H > H)
      throw new Error(
        'Archive boundary is newer than the current backend journal'
      );
    const actual = actualBoundary(backend, identity.missionId, r.source.H);
    if (
      !equalRows(actual.current, r.source.records) ||
      !equalRows(actual.history, r.source.history) ||
      r.inspection.records !== actual.current.length ||
      r.inspection.revisions !== actual.history.length
    )
      throw new Error(
        'Archived revisions do not match complete backend history'
      );
    if (
      zip.sha256 !== r.inspection.zipSha256 ||
      (digest !== undefined && digest !== zip.sha256)
    )
      throw new Error(
        'Select the unchanged original ZIP used in both import comparisons'
      );
    digest = zip.sha256;
    const ready = r.preparations.filter(
      (item) =>
        item.job.state === 'ready' &&
        item.job.mission_id === identity.missionId &&
        item.job.briefing_status === 'included' &&
        item.artifact?.sha256 === zip.sha256 &&
        item.artifact.size === zip.size
    );
    if (!ready.length)
      throw new Error(
        'Selected original ZIP does not match a ready server artifact'
      );
    const required = [
      'operations/journal.json',
      'operations/audit.jsonl',
      'operations/current.json',
      'operations/manifest.json',
      'operations/activity.jsonl',
      'operations/events.json',
      'operations/handover.txt',
      'telemetry/manifest.json',
    ];
    for (const leg of r.inspection.telemetry) {
      if (
        !/^legs\/\d{3}$/.test(leg.path) ||
        !['off_blocks', 'takeoff', 'landed', 'on_blocks'].every((event) =>
          leg.events.includes(event)
        )
      )
        throw new Error('Complete sealed synthetic telemetry required');
      required.push(
        ...['manifest.json', 'events.csv', 'observations.csv'].map(
          (file) => `telemetry/${leg.path}/${file}`
        )
      );
    }
    if (
      new Set(r.inspection.telemetry.map((leg) => leg.path)).size !== 2 ||
      !r.inspection.pdfPath.startsWith('exports/mission/') ||
      !r.inspection.pdfPath.endsWith('-brief.pdf') ||
      r.inspection.checksumReads.some(
        (item) =>
          item.expected !== item.actual ||
          item.path.startsWith('/') ||
          item.path.split('/').includes('..')
      ) ||
      !required.every((path) =>
        r.inspection.checksumReads.some((item) => item.path === path)
      )
    )
      throw new Error(
        'Original archive checksum/PDF/telemetry facts are incomplete or inconsistent'
      );
    const { before, after } = r.transfer;
    if (
      before.health.store_id === identity.storeId ||
      !sameJson(before.health, after.health) ||
      before.H !== after.H ||
      !equalRows(before.records, after.records) ||
      !equalRows(before.history, after.history) ||
      (r.label === 'empty'
        ? before.H !== 0 ||
          before.records.length !== 0 ||
          before.history.length !== 0 ||
          before.missions.length !== 0
        : before.records.length === 0) ||
      before.missions.some((m) => m.id === r.importedMission.id) ||
      !after.missions.some((m) => m.id === r.importedMission.id) ||
      !before.missions.every((m) =>
        after.missions.some((saved) => saved.id === m.id)
      ) ||
      !sameJson(
        r.source.mission.legs.map((l) => [l.name, l.transports]),
        r.importedMission.legs.map((l) => [l.name, l.transports])
      )
    )
      throw new Error(
        'Separate destination import did not preserve its full journal or mission context'
      );
    outcomes.add('export-downloaded');
    outcomes.add('archive-contents-validated');
    if (
      ready.some(
        (item) =>
          item.job.finished_at !== null &&
          r.preparations.some(
            (prior) =>
              prior.job.state === 'cancelled' &&
              prior.job.mission_id === identity.missionId &&
              prior.job.id !== item.job.id &&
              prior.job.fingerprint === item.job.fingerprint &&
              prior.job.finished_at !== null &&
              prior.job.finished_at <= item.job.queued_at
          )
      )
    )
      outcomes.add('export-cancel-recovery');
  }
  if (observations.length === 2) outcomes.add('archive-imported-isolated');
  return [...outcomes];
}
