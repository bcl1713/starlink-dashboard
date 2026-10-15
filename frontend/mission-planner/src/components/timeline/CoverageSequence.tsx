import type { Timeline } from '../../services/timeline';
import { formatElapsed, formatUtc } from './formatting';

export function CoverageSequence({ timeline }: { timeline: Timeline | null }) {
  const events = timeline?.coverage_events;
  if (!events?.length) return null;
  const start = timeline?.segments[0]?.start_time ?? events[0].timestamp;
  return (
    <div className="mb-6">
      <h4 className="mb-2 font-semibold text-foreground">
        Ka coverage sequence
      </h4>
      <p className="mb-2 text-xs text-muted-foreground">
        Footprints show modeled availability. Recommended handoffs have separate
        transition buffers below. Boundary times are estimated from minute
        samples.
      </p>
      <div className="overflow-x-auto">
        <table aria-label="Ka coverage sequence" className="w-full text-sm">
          <thead className="bg-muted/70">
            <tr>
              <th className="px-3 py-2 text-left">Time (UTC)</th>
              <th className="px-3 py-2 text-left">Elapsed</th>
              <th className="px-3 py-2 text-left">Coverage change</th>
              <th className="px-3 py-2 text-left">Available footprints</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {events.map((event, index) => (
              <tr
                key={`${event.timestamp}-${index}`}
                className="text-foreground"
              >
                <td className="px-3 py-2 font-mono text-xs">
                  {formatUtc(event.timestamp)}
                </td>
                <td className="px-3 py-2 text-xs">
                  {formatElapsed(event.timestamp, start)}
                </td>
                <td className="px-3 py-2">{event.reason}</td>
                <td className="px-3 py-2">
                  {event.coverage.join(', ') || 'Unavailable'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
