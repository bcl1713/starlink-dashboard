import type { Scope } from '@/types/operator';
export interface TimedLeg {
  id: string;
  name: string;
  start: string | null;
  end: string | null;
}
export interface CallAssociation {
  scope: Scope;
  leg_id: string | null;
  previous_leg_id: string | null;
  next_leg_id: string | null;
  label: string;
}
/** Require the complete, ordered itinerary before inferring a phase. */
export function inferCallAssociation(
  legs: TimedLeg[],
  at: string | null
): CallAssociation | null {
  const time = Date.parse(at ?? '');
  if (!Number.isFinite(time) || !legs.length) return null;
  const intervals = legs.map((leg) => ({
    ...leg,
    from: Date.parse(leg.start ?? ''),
    to: Date.parse(leg.end ?? ''),
  }));
  if (
    intervals.some(
      (leg, index) =>
        !Number.isFinite(leg.from) ||
        !Number.isFinite(leg.to) ||
        leg.to <= leg.from ||
        (index > 0 && leg.from < intervals[index - 1].to)
    )
  )
    return null;
  const result = (
    scope: Scope,
    label: string,
    leg_id: string | null = null,
    previous_leg_id: string | null = null,
    next_leg_id: string | null = null
  ): CallAssociation => ({
    scope,
    label,
    leg_id,
    previous_leg_id,
    next_leg_id,
  });
  if (time < intervals[0].from) return result('preflight', 'Preflight');
  for (let i = 0; i < intervals.length; i++) {
    const leg = intervals[i];
    if (time >= leg.from && time < leg.to)
      return result('leg', leg.name, leg.id);
    const next = intervals[i + 1];
    if (next && time >= leg.to && time < next.from)
      return result(
        'between_legs',
        `Between ${leg.name} and ${next.name}`,
        null,
        leg.id,
        next.id
      );
  }
  return result('postflight', 'Postflight');
}
