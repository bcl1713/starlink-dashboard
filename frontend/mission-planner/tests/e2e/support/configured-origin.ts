function requireAbsoluteBaseURL(baseURL: string | undefined): URL {
  if (!baseURL) {
    throw new Error('Playwright project.use.baseURL must be configured');
  }

  const parsed = new URL(baseURL);
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('Playwright baseURL must use http or https');
  }

  return parsed;
}

function requirePathname(pathname: string): void {
  if (!pathname.startsWith('/')) {
    throw new Error('Route pathname must begin with /');
  }
}

export function configuredOrigin(baseURL: string | undefined): string {
  return requireAbsoluteBaseURL(baseURL).origin;
}

export function routeUrl(
  baseURL: string | undefined,
  pathname: string
): string {
  requirePathname(pathname);
  return `${configuredOrigin(baseURL)}${pathname}`;
}

export function routeGlob(
  baseURL: string | undefined,
  pathname: string
): string {
  return `${routeUrl(baseURL, pathname)}**`;
}

export function requestUrlPattern(
  baseURL: string | undefined,
  pathname: string
): RegExp {
  const escaped = routeUrl(baseURL, pathname).replace(
    /[.*+?^${}()|[\]\\]/g,
    '\\$&'
  );

  return new RegExp(`^${escaped}(?:\\?|$)`);
}
