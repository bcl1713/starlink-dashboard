import type { RetentionOutcome } from './overview-lifecycle-types';

export const EVIDENCE_LIMITS = {
  cdpEvents: 240,
  cdpRecords: 80,
  pendingReports: 240,
  lifecycleMutations: 240,
  lifecycleSamples: 256,
  identityTransitions: 80,
  mutationNodes: 4,
  artifactBytes: 256 * 1024,
  screenshotBytes: 2 * 1024 * 1024,
} as const;

export function appendBounded<T>(
  values: T[],
  value: T,
  limit: number,
  label: string,
  overflowed: Set<string>
) {
  if (values.length < limit) values.push(value);
  else overflowed.add(label);
}

export function retentionOutcome(
  overflowed: ReadonlySet<string>,
  retained: Readonly<Record<string, number>>
): RetentionOutcome {
  return {
    status: overflowed.size ? 'overflow' : 'complete',
    overflowed: [...overflowed].sort(),
    retained,
  };
}
