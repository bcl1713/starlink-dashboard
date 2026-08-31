import { mkdir, writeFile } from 'node:fs/promises';
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
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, name), body);
}
