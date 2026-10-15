export interface Challenger {
  id: string;
  count: number;
}
export function advanceHysteresis(
  current: string | null,
  candidate: string | null,
  improvement: number,
  threshold: number,
  previous: Challenger | null,
  currentValid: boolean
): { selected: string | null; challenger: Challenger | null } {
  if (!currentValid || !current)
    return { selected: candidate, challenger: null };
  if (!candidate || candidate === current || improvement + 1e-10 < threshold)
    return { selected: current, challenger: null };
  const count = previous?.id === candidate ? previous.count + 1 : 1;
  return count >= 2
    ? { selected: candidate, challenger: null }
    : { selected: current, challenger: { id: candidate, count } };
}
