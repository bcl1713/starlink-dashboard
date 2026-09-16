interface OverviewHistoryStateInput {
  isLoading: boolean;
  isError: boolean;
  pointCount: number;
}
export function overviewHistoryState({
  isLoading,
  isError,
  pointCount,
}: OverviewHistoryStateInput) {
  if (isError) {
    return 'Aircraft history unavailable';
  }
  if (isLoading) {
    return 'Loading aircraft history…';
  }
  if (pointCount === 0) {
    return 'No aircraft history';
  }
  return `${pointCount} trail points`;
}
