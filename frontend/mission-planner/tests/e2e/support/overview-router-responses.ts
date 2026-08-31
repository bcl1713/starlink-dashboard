import type { Route } from '@playwright/test';

export const radarPng = Uint8Array.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49,
  0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06,
  0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44,
  0x41, 0x54, 0x78, 0x9c, 0x63, 0xf8, 0xcf, 0xc0, 0xf0, 0x1f, 0x00, 0x05, 0x00,
  0x01, 0xff, 0x89, 0x99, 0x3d, 0x1d, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
  0x44, 0xae, 0x42, 0x60, 0x82,
]);

const basemapSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">
  <rect width="256" height="256" fill="#15202b"/>
  <path d="M0 32H256M0 96H256M0 160H256M0 224H256M32 0V256M96 0V256M160 0V256M224 0V256" stroke="#334155" stroke-width="3"/>
  <path d="M0 190C64 150 96 210 160 170S224 120 256 150" fill="none" stroke="#38bdf8" stroke-width="10"/>
  <path d="M20 40L86 70L58 124L132 104L172 44L222 88L204 142L244 206L136 232L72 184Z" fill="#365314" opacity=".85"/>
</svg>`;

export function jsonResponse(id: string, json: unknown) {
  return {
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
      'x-correlation-id': id,
    },
    json,
  };
}

export function errorResponse(id: string, status: number, detail: string) {
  return {
    status,
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
      'x-correlation-id': id,
    },
    json: { detail },
  };
}

export async function fulfillSourceError(
  route: Route,
  id: string,
  status: number,
  detail: string
) {
  await route.fulfill(errorResponse(id, status, detail));
  return { status };
}

export async function fulfillPng(route: Route, id: string, frame: string) {
  await route.fulfill({
    body: Buffer.from(radarPng),
    headers: {
      'cache-control': 'public, max-age=60',
      'content-type': 'image/png',
      'x-correlation-id': id,
      'x-radar-frame-timestamp': frame,
    },
  });
  return { status: 200 };
}

export async function fulfillBasemap(route: Route, id: string) {
  await route.fulfill({
    body: Buffer.from(basemapSvg),
    headers: {
      'cache-control': 'public, max-age=60',
      'content-type': 'image/svg+xml',
      'x-correlation-id': id,
    },
  });
  return { status: 200 };
}
