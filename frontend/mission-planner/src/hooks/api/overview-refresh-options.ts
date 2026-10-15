/** Opt Overview's observers into saved-state refresh without changing editors. */
export function overviewRefreshOptions(live: boolean) {
  return live
    ? {
        refetchInterval: 5_000,
        refetchIntervalInBackground: true,
        refetchOnWindowFocus: 'always' as const,
        refetchOnReconnect: 'always' as const,
      }
    : {};
}
