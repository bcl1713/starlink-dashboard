import type { DisplayResult } from '@/services/overview-display-protocol';

export async function requestOverviewFullscreen(): Promise<DisplayResult> {
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
