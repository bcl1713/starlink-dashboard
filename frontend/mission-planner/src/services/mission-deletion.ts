import { isAxiosError } from 'axios';

const ACTIVE_DELETION_CODES = new Set([
  'ACTIVE_LEG_DELETION_FORBIDDEN',
  'ACTIVE_MISSION_DELETION_FORBIDDEN',
]);

export function formatMissionDeletionError(error: unknown): string {
  if (!isAxiosError(error)) {
    return 'Failed to delete. Please try again.';
  }

  const detail = error.response?.data?.detail;
  if (
    detail &&
    typeof detail === 'object' &&
    'code' in detail &&
    'action' in detail &&
    typeof detail.code === 'string' &&
    typeof detail.action === 'string' &&
    ACTIVE_DELETION_CODES.has(detail.code)
  ) {
    return detail.action;
  }

  return 'Failed to delete. Please try again.';
}
