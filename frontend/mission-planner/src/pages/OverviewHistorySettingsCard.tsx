import { Card } from '@/components/ui/card';
import { useOverviewHistorySettings } from '@/hooks/api/useOverviewHistorySettings';
import { useUpdateOverviewHistorySettings } from '@/hooks/api/useUpdateOverviewHistorySettings';

const HISTORY_WINDOWS = [300, 900, 1800, 3600];

/** The persisted window applies to both the aircraft trail and network graphs. */
export function OverviewHistorySettingsCard({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  const { data, isLoading, isError } = useOverviewHistorySettings();
  const {
    mutate,
    isPending,
    isError: saveError,
  } = useUpdateOverviewHistorySettings();
  const custom = data && !HISTORY_WINDOWS.includes(data.window_seconds);
  const content = (
    <section
      className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3 py-4"
      aria-label="Overview history settings"
    >
      <div className="min-w-0 flex-1">
        <label
          htmlFor="overview-history-window"
          className="text-sm font-medium"
        >
          Overview history window
        </label>
        <p className="mt-1 max-w-xl text-sm text-muted-foreground">
          Applies to the aircraft trail and all five network graphs. Rolling
          statistics use five minutes.
        </p>
      </div>
      <select
        id="overview-history-window"
        className="min-h-11 rounded-md border bg-background px-3 text-sm"
        value={data ? String(data.window_seconds) : ''}
        disabled={!data || isLoading || isError || isPending}
        onChange={(event) => {
          const seconds = Number(event.target.value);
          if (Number.isInteger(seconds) && seconds > 0) mutate(seconds);
        }}
      >
        {!data && (
          <option value="" disabled>
            {isError ? 'Unavailable' : 'Loading…'}
          </option>
        )}
        {custom && (
          <option value={data.window_seconds}>
            {data.window_seconds} seconds
          </option>
        )}
        {HISTORY_WINDOWS.map((seconds) => (
          <option key={seconds} value={seconds}>
            {seconds / 60} minutes
          </option>
        ))}
      </select>
      {isLoading && <p role="status">Loading Overview history settings…</p>}
      {isError && <p role="alert">Overview history settings unavailable</p>}
      {saveError && (
        <p role="alert">
          Unable to save Overview history window. Please try again.
        </p>
      )}
      {isPending && <p role="status">Saving Overview history window…</p>}
    </section>
  );
  return embedded ? content : <Card className="px-6">{content}</Card>;
}
