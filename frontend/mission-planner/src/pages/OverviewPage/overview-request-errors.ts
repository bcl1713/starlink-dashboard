import axios from 'axios';

import type { OverviewSourceError } from './overview-data-types';

export const REQUEST_FAILED_ERROR = {
  code: 'request-failed',
  message: 'Source refresh failed.',
} as const;

export function classifyOverviewError(
  error: unknown,
  signalAborted: boolean
): OverviewSourceError | null {
  if (signalAborted || safeIsCancel(error)) return null;
  if (
    safeGet(error, 'name') === 'OverviewDataValidationError' &&
    safeGet(error, 'code') === 'invalid_overview_data' &&
    typeof safeGet(error, 'source') === 'string'
  ) {
    return { code: 'invalid-data', message: 'Source data was invalid.' };
  }
  return REQUEST_FAILED_ERROR;
}

function safeIsCancel(error: unknown): boolean {
  try {
    return axios.isCancel(error);
  } catch {
    return false;
  }
}

function safeGet(value: unknown, key: string): unknown {
  if (value === null) return undefined;
  const kind = typeof value;
  if (kind !== 'object' && kind !== 'function') return undefined;
  try {
    return Reflect.get(value as object, key);
  } catch {
    return undefined;
  }
}
