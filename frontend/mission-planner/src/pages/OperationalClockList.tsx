import type { OverviewClockSetting } from '@/services/overview-clock-settings';
import { OperationalClock } from './OperationalClock';
interface OperationalClockListProps {
  clocks: readonly OverviewClockSetting[];
  currentTime: number;
}
export function OperationalClockList({
  clocks,
  currentTime,
}: OperationalClockListProps) {
  return (
    <section className="operational-clock-list" aria-label="Operational clocks">
      {clocks.map((clock) => (
        <OperationalClock
          key={`${clock.label}-${clock.time_zone}`}
          label={clock.label}
          timeZone={clock.time_zone}
          currentTime={currentTime}
        />
      ))}
    </section>
  );
}
