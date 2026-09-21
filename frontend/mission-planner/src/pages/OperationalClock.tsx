import { formatOperationalClockTime } from './operational-clock-format';
interface OperationalClockProps {
  label: string;
  timeZone: string;
  currentTime: number;
}
export function OperationalClock({
  label,
  timeZone,
  currentTime,
}: OperationalClockProps) {
  return (
    <section
      className="operational-clock"
      aria-label={`${label} operational clock`}
    >
      <p className="operational-clock__label">{label}</p>
      <time
        className="operational-clock__time"
        dateTime={new Date(currentTime).toISOString()}
      >
        {formatOperationalClockTime(currentTime, timeZone)}
      </time>
    </section>
  );
}
