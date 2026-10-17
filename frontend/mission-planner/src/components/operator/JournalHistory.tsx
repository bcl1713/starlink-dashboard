import { useInfiniteQuery } from '@tanstack/react-query';
import { readOperatorHistory } from '@/services/operator';
export function JournalHistory({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const history = useInfiniteQuery({
    queryKey: ['operator-history', id],
    queryFn: ({ pageParam }) => readOperatorHistory(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    retry: false,
  });
  return (
    <section
      aria-label="Entry history"
      className="min-w-0 space-y-3 break-words rounded-lg border bg-card p-4 [overflow-wrap:anywhere]"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Entry history</h2>
        <button className="min-h-11 border px-3" onClick={onClose}>
          Close history
        </button>
      </div>
      {history.isPending && <p>Loading history…</p>}
      {history.isError && (
        <p role="alert">
          History unavailable.{' '}
          <button onClick={() => void history.refetch()}>Retry history</button>
        </p>
      )}
      <ol className="space-y-4">
        {history.data?.pages
          .flatMap((page) => page.items)
          .map(({ record }) => (
            <li key={record.version} className="space-y-1 border-t pt-3">
              <p>
                Version {record.version} · {record.operation} ·{' '}
                {record.recorded_at} (UTC)
              </p>
              <h3 className="font-semibold">{record.payload.title}</h3>
              <p className="whitespace-pre-wrap">{record.payload.note}</p>
              {record.reason && (
                <p>
                  {record.reason_origin === 'operator'
                    ? 'Operator-authored'
                    : 'Automatic'}{' '}
                  reason: {record.reason}
                </p>
              )}
            </li>
          ))}
      </ol>
      {history.hasNextPage && (
        <button
          className="min-h-11 border px-3"
          disabled={history.isFetchingNextPage}
          onClick={() => void history.fetchNextPage()}
        >
          More history
        </button>
      )}
    </section>
  );
}
