import type { OverviewClockSetting } from '@/services/overview-clock-settings';
import { OperationalClockList } from './OperationalClockList';
interface OverviewClockPanelProps {
  clocks: readonly OverviewClockSetting[] | undefined;
  currentTime: number;
  isError: boolean;
  isLoading: boolean;
}
export function OverviewClockPanel({
  clocks,
  currentTime,
  isError,
  isLoading,
}: OverviewClockPanelProps) {
  if (isError) {
    return (
      <aside
        className="overview-clock-panel"
        aria-label="Operational clocks"
        role="alert"
      >
        <p>Operational clocks unavailable</p>
      </aside>
    );
  }
  if (isLoading) {
    return (
      <aside className="overview-clock-panel" aria-label="Operational clocks">
        <p>Loading operational clocks...</p>
      </aside>
    );
  }
  if (!clocks) {
    return (
      <aside
        className="overview-clock-panel"
        aria-label="Operational clocks"
        role="alert"
      >
        <p>Operational clocks unavailable</p>
      </aside>
    );
  }
  return (
    <aside className="overview-clock-panel" aria-label="Operational clocks">
      <OperationalClockList clocks={clocks} currentTime={currentTime} />
    </aside>
  );
}
