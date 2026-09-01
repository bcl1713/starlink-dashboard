import { createHash } from 'node:crypto';
import {
  lstat,
  mkdir,
  readdir,
  readFile,
  stat,
  writeFile,
} from 'node:fs/promises';
import path from 'node:path';

import { EVIDENCE_LIMITS } from './overview-evidence-limits';

export async function writeOverviewArtifact(
  name: string,
  body: Buffer | string,
  maxBytes = typeof body === 'string'
    ? EVIDENCE_LIMITS.artifactBytes
    : EVIDENCE_LIMITS.screenshotBytes
) {
  const dir = process.env.OVERVIEW_ARTIFACT_DIR;
  if (!dir) return;
  const bytes = Buffer.byteLength(body);
  if (bytes > maxBytes) {
    throw new Error(
      `Overview artifact budget exceeded: ${name} is ${bytes} bytes; limit is ${maxBytes}`
    );
  }
  await ensureSecureDirectory(dir);
  const target = path.join(dir, safeArtifactName(name));
  await rejectInsecureExistingArtifact(target);
  await writeFile(target, body, { mode: 0o600 });
  await ensureMode(target, 0o600, 'evidence artifact');
  await writeManifest(dir);
}

export async function validateOverviewArtifactManifest(
  dir = process.env.OVERVIEW_ARTIFACT_DIR
) {
  if (!dir) return;
  await ensureSecureDirectory(dir);
  const manifest = JSON.parse(
    await readFile(path.join(dir, 'manifest.json'), 'utf8')
  ) as {
    readonly artifacts: readonly {
      readonly name: string;
      readonly bytes: number;
      readonly sha256: string;
    }[];
  };
  const names = (await readdir(dir))
    .filter((name) => name !== 'manifest.json')
    .sort();
  if (
    JSON.stringify(names) !==
    JSON.stringify(manifest.artifacts.map((entry) => entry.name).sort())
  )
    throw new Error('Evidence manifest inventory mismatch');
  for (const entry of manifest.artifacts) {
    const target = path.join(dir, safeArtifactName(entry.name));
    await ensureMode(target, 0o600, 'evidence artifact');
    const body = await readFile(target);
    if (body.length !== entry.bytes || digest(body) !== entry.sha256)
      throw new Error(`Evidence manifest checksum mismatch: ${entry.name}`);
  }
}

async function ensureSecureDirectory(dir: string) {
  await mkdir(dir, { recursive: true, mode: 0o700 });
  await ensureMode(dir, 0o700, 'evidence directory');
}

async function rejectInsecureExistingArtifact(target: string) {
  try {
    const existing = await lstat(target);
    if (!existing.isFile() || (existing.mode & 0o777) !== 0o600)
      throw new Error(`Insecure evidence artifact: ${path.basename(target)}`);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
}

async function ensureMode(target: string, expected: number, label: string) {
  const details = await stat(target);
  if ((details.mode & 0o777) !== expected)
    throw new Error(`Insecure ${label}: ${target}`);
}

function safeArtifactName(name: string) {
  if (path.basename(name) !== name || name === 'manifest.json')
    throw new Error(`Invalid evidence artifact name: ${name}`);
  return name;
}

async function writeManifest(dir: string) {
  const artifacts = await Promise.all(
    (await readdir(dir))
      .filter((name) => name !== 'manifest.json')
      .sort()
      .map(async (name) => {
        const target = path.join(dir, safeArtifactName(name));
        await ensureMode(target, 0o600, 'evidence artifact');
        const body = await readFile(target);
        return { name, bytes: body.length, sha256: digest(body) };
      })
  );
  const target = path.join(dir, 'manifest.json');
  await rejectInsecureExistingArtifact(target);
  await writeFile(target, `${JSON.stringify({ artifacts }, null, 2)}\n`, {
    mode: 0o600,
  });
  await ensureMode(target, 0o600, 'evidence artifact');
  await validateOverviewArtifactManifest(dir);
}

function digest(body: Buffer) {
  return createHash('sha256').update(body).digest('hex');
}
