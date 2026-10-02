import { useOverviewHistorySettings } from '@/hooks/api/useOverviewHistorySettings';
import { useUpdateOverviewHistorySettings } from '@/hooks/api/useUpdateOverviewHistorySettings';

const HISTORY_WINDOWS = [300, 900, 1800, 3600];

/** The persisted window applies to both the aircraft trail and network graphs. */
export function OverviewHistorySettingsCard() {
  const { data, isLoading, isError } = useOverviewHistorySettings();
  const {
    mutate,
    isPending,
    isError: saveError,
  } = useUpdateOverviewHistorySettings();
  const custom = data && !HISTORY_WINDOWS.includes(data.window_seconds);
  return (
    <section
      className="mt-6 rounded-lg border p-4"
      aria-label="Overview history settings"
    >
      <h2 className="text-xl font-semibold">Overview history</h2>
      <p className="my-2">
        The display window applies to the aircraft trail and all five network
        graphs. Rolling statistics always use five minutes.
      </p>
      <label htmlFor="overview-history-window" className="block mb-2">
        Overview history window
      </label>
      <select
        id="overview-history-window"
        className="rounded border bg-background p-2"
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
}
