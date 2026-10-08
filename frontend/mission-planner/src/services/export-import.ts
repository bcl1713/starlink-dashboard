import { apiClient } from './api-client';
import axios from 'axios';
import type { ImportResult, MissionExportResult } from '../types/export';

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

const TRIAL_FAILURE_WARNING =
  'Customer briefing — Trial could not be generated. Legacy exports are included.';

function exportWarnings(header: unknown): string[] {
  // A malformed or oversized feedback header must never block the ZIP download.
  if (typeof header !== 'string' || header.length > 2048) return [];
  try {
    const value: unknown = JSON.parse(header);
    if (!Array.isArray(value) || value.length > 8) return [];
    return value.filter(
      (warning): warning is string =>
        typeof warning === 'string' &&
        warning.length > 0 &&
        warning.length <= 256 &&
        Array.from(warning).every((character) => {
          const code = character.charCodeAt(0);
          return code >= 32 && code !== 127;
        })
    );
  } catch {
    return [];
  }
}

export const exportImportApi = {
  exportMissionResult: async (
    missionId: string
  ): Promise<MissionExportResult> => {
    const response = await apiClient.post(
      `/api/v2/missions/${missionId}/export`,
      {},
      {
        responseType: 'blob',
      }
    );
    const warnings = exportWarnings(
      response.headers?.['x-mission-export-warnings']
    );
    if (response.headers?.['x-mission-export-trial-status'] === 'failed') {
      if (!warnings.includes(TRIAL_FAILURE_WARNING))
        warnings.unshift(TRIAL_FAILURE_WARNING);
    }
    return { blob: response.data, warnings };
  },

  exportMission: async (missionId: string): Promise<Blob> => {
    return (await exportImportApi.exportMissionResult(missionId)).blob;
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
