/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { requestOverviewFullscreen } from './overview-fullscreen';

afterEach(() => {
  Reflect.deleteProperty(document, 'fullscreenElement');
  Reflect.deleteProperty(document.documentElement, 'requestFullscreen');
});
function fullscreen(element: Element | null) {
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    value: element,
  });
}
function request(fn: () => Promise<void>) {
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: fn,
  });
}
it('already-fullscreen returns accepted without another native request', async () => {
  const native = vi.fn();
  fullscreen(document.documentElement);
  request(native);
  expect(await requestOverviewFullscreen()).toBe('accepted');
  expect(native).not.toHaveBeenCalled();
});
it('missing API reports unsupported', async () => {
  expect(await requestOverviewFullscreen()).toBe('unsupported');
});
it('fullscreen rejection gives a local-click fallback', async () => {
  request(async () => {
    throw new TypeError('Permissions check failed');
  });
  expect(await requestOverviewFullscreen()).toBe('interaction-required');
});
it('synchronous native rejection is also handled', async () => {
  request(() => {
    throw new TypeError('Denied');
  });
  expect(await requestOverviewFullscreen()).toBe('interaction-required');
});
it('native fulfillment only accepts actual root fullscreen', async () => {
  request(async () => {
    fullscreen(document.documentElement);
  });
  expect(await requestOverviewFullscreen()).toBe('accepted');
});
it.each([null, document.body])(
  'fulfillment without root fullscreen never claims entry (%s)',
  async (element) => {
    request(async () => {
      fullscreen(element);
    });
    expect(await requestOverviewFullscreen()).toBe('interaction-required');
  }
);
