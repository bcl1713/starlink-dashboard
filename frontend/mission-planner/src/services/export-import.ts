import { apiClient } from './api-client';
import axios from 'axios';
import type { ImportResult, MissionExportDownload } from '../types/export';

const briefingWarnings = new Set([
  'snapshot',
  'data',
  'page-budget',
  'overflow',
  'runtime',
  'deadline',
  'pdf',
  'evidence',
  'cleanup',
  'publication',
  'busy',
]);

async function exportMissionDownload(
  missionId: string,
  options: { signal?: AbortSignal } = {}
): Promise<MissionExportDownload> {
  const response = await apiClient.post(
    `/api/v2/missions/${missionId}/export`,
    {},
    {
      responseType: 'blob',
      signal: options.signal,
    }
  );
  const status = response.headers?.['x-customer-briefing-status'];
  const briefingStatus =
    status === 'included' || status === 'omitted' ? status : undefined;
  const warning = response.headers?.['x-customer-briefing-warning'];
  const warningCode =
    briefingStatus === 'omitted'
      ? typeof warning === 'string' && briefingWarnings.has(warning)
        ? warning
        : 'runtime'
      : undefined;
  return { blob: response.data, briefingStatus, warningCode };
}

interface MissionPackageTooLargeDetail {
  code: 'mission_package_too_large';
  layer: string;
  max_bytes: number;
}

export function formatMissionImportError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail as
      | MissionPackageTooLargeDetail
      | undefined;

    if (detail?.code === 'mission_package_too_large') {
      const maxMiB = detail.max_bytes / (1024 * 1024);
      return `Mission package exceeds the ${maxMiB} MiB limit (rejected by ${detail.layer}).`;
    }

    return error.message;
  }

  return error instanceof Error ? error.message : 'Unknown error';
}

export const exportImportApi = {
  exportMissionDownload,
  exportMission: async (missionId: string): Promise<Blob> => {
    return (await exportMissionDownload(missionId)).blob;
  },

  importMission: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<ImportResult>(
      '/api/v2/missions/import',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },
};
