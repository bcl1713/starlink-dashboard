export type FullscreenResult =
  | 'accepted'
  | 'unsupported'
  | 'interaction-required';

export async function requestOverviewFullscreen(): Promise<FullscreenResult> {
  const root = document.documentElement;
  if (document.fullscreenElement === root) return 'accepted';
  if (typeof root.requestFullscreen !== 'function') return 'unsupported';
  try {
    // Invoke before the first await so local clicks retain transient activation.
    await root.requestFullscreen();
    return document.fullscreenElement === root
      ? 'accepted'
      : 'interaction-required';
  } catch {
    return 'interaction-required';
  }
}
