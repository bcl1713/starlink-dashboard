import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

export async function writeOverviewArtifact(
  name: string,
  body: Buffer | string
) {
  const dir = process.env.OVERVIEW_ARTIFACT_DIR;
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, name), body);
}
