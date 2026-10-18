import { useInfiniteQuery } from '@tanstack/react-query';
import { readOperatorHistory } from '@/services/operator';
import type { SavedRecord } from '@/types/operator';
import { projectIssueActivity } from './issueActivity';
import { operatorUtc } from './issueForms';
import { issueButton } from './issueForms';
export function IssueActivity({
  id,
  identity,
  onCorrect,
  disabled,
}: {
  id: string;
  identity: string;
  onCorrect: (record: SavedRecord) => void;
  disabled: boolean;
}) {
  const history = useInfiniteQuery({
    queryKey: ['operator-history', identity, id],
    queryFn: ({ pageParam }) => readOperatorHistory(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.cursor ?? undefined,
    retry: false,
  });
  const records =
    history.data?.pages.flatMap((p) => p.items.map((i) => i.record)) ?? [];
  if (history.isPending) return <p>Loading issue activity…</p>;
  if (history.isError)
    return (
      <p role="alert">
        Issue activity unavailable.{' '}
        <button onClick={() => void history.refetch()}>Retry activity</button>
      </p>
    );
  if (history.hasNextPage)
    return (
      <p>
        Activity incomplete.{' '}
        <button
          className={issueButton}
          onClick={() => void history.fetchNextPage()}
        >
          Load remaining activity
        </button>
      </p>
    );
  let result;
  try {
    result = projectIssueActivity(records);
  } catch {
    return (
      <p role="alert">
        Activity incomplete; refresh to reconcile correction history.
      </p>
    );
  }
  return (
    <section aria-label="Issue activity" className="space-y-3">
      <p>
        Operational updates · corrections shown once. Audit retains all
        revisions.
      </p>
      <ol className="space-y-3">
        {result.updates.map((item) => (
          <li key={item.rootVersion} className="border-t pt-2">
            <p>{operatorUtc(item.effectiveAt)} · Operator reported</p>
            <p className="whitespace-pre-wrap">{item.text}</p>
            <p className="text-sm">
              {item.corrected ? 'Corrected · ' : ''}
              {item.effectiveAt &&
              Date.parse(item.effectiveAt) < Date.parse(item.recordedAt)
                ? 'Entered later · '
                : ''}
              Recorded {operatorUtc(item.recordedAt)}
            </p>
            <button
              className={issueButton}
              disabled={disabled}
              onClick={() => onCorrect(item.selected)}
            >
              Correct this update
            </button>
          </li>
        ))}
      </ol>
      <p className="font-medium">Lifecycle</p>
      <ol>
        {result.lifecycle.map((item) => (
          <li key={item.record.version}>
            {item.status} · {operatorUtc(item.record.time.occurred_at)}
          </li>
        ))}
      </ol>
    </section>
  );
}
