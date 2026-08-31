export interface EvidenceProvenance {
  readonly commitSha: string;
  readonly branch: string;
  readonly ref: string;
  readonly cleanWorktree: true;
  readonly producer: {
    readonly name: 'mission-planner-playwright';
    readonly node: string;
    readonly playwright: string;
  };
  readonly browser: {
    readonly engine: 'chromium';
    readonly executablePath: string;
  };
  readonly captureStartedAtUtc: string;
  readonly captureFinishedAtUtc: string;
}

const required = [
  'OVERVIEW_EVIDENCE_COMMIT_SHA',
  'OVERVIEW_EVIDENCE_BRANCH',
  'OVERVIEW_EVIDENCE_REF',
  'OVERVIEW_EVIDENCE_CLEAN_WORKTREE',
  'OVERVIEW_EVIDENCE_CAPTURE_STARTED_AT_UTC',
] as const;

export function captureEvidenceProvenance(): EvidenceProvenance | undefined {
  if (!process.env.OVERVIEW_ARTIFACT_DIR) return undefined;
  for (const key of required) {
    if (!process.env[key])
      throw new Error(`Missing durable evidence field: ${key}`);
  }
  if (process.env.OVERVIEW_EVIDENCE_CLEAN_WORKTREE !== 'true') {
    throw new Error('Durable evidence requires a clean worktree assertion');
  }
  const commitSha = process.env.OVERVIEW_EVIDENCE_COMMIT_SHA!;
  if (!/^[0-9a-f]{40}$/i.test(commitSha)) {
    throw new Error('Durable evidence requires a full 40-character commit SHA');
  }
  const artifactDir = process.env.OVERVIEW_ARTIFACT_DIR;
  if (!artifactDir.includes(`/${commitSha}/task-13`)) {
    throw new Error(
      'Durable evidence directory must be SHA-qualified Task 13 root'
    );
  }
  return {
    commitSha,
    branch: process.env.OVERVIEW_EVIDENCE_BRANCH!,
    ref: process.env.OVERVIEW_EVIDENCE_REF!,
    cleanWorktree: true,
    producer: {
      name: 'mission-planner-playwright',
      node: process.version,
      playwright:
        process.env.npm_package_devDependencies__playwright ?? 'locked',
    },
    browser: {
      engine: 'chromium',
      executablePath:
        process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? 'managed',
    },
    captureStartedAtUtc: process.env.OVERVIEW_EVIDENCE_CAPTURE_STARTED_AT_UTC!,
    captureFinishedAtUtc: new Date().toISOString(),
  };
}
