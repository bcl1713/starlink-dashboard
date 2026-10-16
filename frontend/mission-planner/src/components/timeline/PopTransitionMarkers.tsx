import type { PopForecast, PopTransition } from '@/types/pop';
import { popCities } from '@/pages/pop-advisory-projection';
import { formatUtc } from './formatting';

interface Props {
  forecast?: PopForecast | null;
  startUtc?: string;
  endUtc?: string;
  onSelect: (transition: PopTransition) => void;
}
/** Empty outlined buttons; all visible descriptions belong outside this track. */
export function PopTransitionMarkers({
  forecast,
  startUtc,
  endUtc,
  onSelect,
}: Props) {
  const start = Date.parse(startUtc ?? ''),
    end = Date.parse(endUtc ?? '');
  if (
    forecast?.status !== 'ready' ||
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    end <= start
  )
    return null;
  const lanes: number[] = [];
  const markers = [...forecast.transitions]
    .sort(
      (a, b) => Date.parse(a.window_start_utc) - Date.parse(b.window_start_utc)
    )
    .flatMap((transition) => {
      const left = Math.max(start, Date.parse(transition.window_start_utc));
      const right = Math.min(end, Date.parse(transition.window_end_utc));
      if (!Number.isFinite(left) || !Number.isFinite(right) || right <= left)
        return [];
      let lane = lanes.findIndex((last) => last <= left);
      if (lane < 0) lane = lanes.length;
      lanes[lane] = right;
      return [{ transition, left, right, lane }];
    });
  return (
    <div
      data-pop-track
      className="pointer-events-none relative w-full"
      style={{ height: `${Math.max(1, lanes.length) * 44}px` }}
    >
      {markers.map(({ transition, left, right, lane }) => (
        <button
          key={transition.crossing.id}
          type="button"
          className="pointer-events-auto absolute min-h-11 rounded border-2 border-dashed border-amber-600 bg-transparent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          style={{
            left: `${(100 * (left - start)) / (end - start)}%`,
            width: `${(100 * (right - left)) / (end - start)}%`,
            top: `${lane * 44}px`,
          }}
          aria-label={`${popCities(transition)}. Estimated crossing UTC ${formatUtc(transition.crossing_utc)}. Possible call interruption. Window UTC ${formatUtc(transition.window_start_utc)} to ${formatUtc(transition.window_end_utc)}`}
          onClick={() => onSelect(transition)}
        />
      ))}
    </div>
  );
}
