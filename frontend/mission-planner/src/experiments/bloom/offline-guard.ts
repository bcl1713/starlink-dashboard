import { allowRequest } from './contracts';

// Installed before importing any scene code. CSP on the standalone server is
// the independent browser-enforced guard (connect-src 'none', no form actions).
export function installOfflineGuard() {
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname)) {
    throw new Error('The bloom experiment requires a loopback origin.');
  }
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = input instanceof Request ? input.url : String(input);
    const method =
      init?.method ?? (input instanceof Request ? input.method : 'GET');
    if (!allowRequest(url, method, location.origin)) {
      return Promise.reject(new Error('Offline experiment blocked request'));
    }
    return originalFetch(input, init);
  };
  const blocked = class {
    constructor() {
      throw new Error('Offline experiment blocked transport');
    }
  };
  Object.defineProperties(window, {
    XMLHttpRequest: { value: blocked },
    WebSocket: { value: blocked },
    EventSource: { value: blocked },
  });
  Object.defineProperty(navigator, 'sendBeacon', { value: () => false });
}
