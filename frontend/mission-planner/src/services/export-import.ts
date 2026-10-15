import { apiClient } from './api-client';
import axios from 'axios';
import type {
  ExportPreparation,
  ImportResult,
  MissionExportDownload,
} from '../types/export';

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

interface ExportOptions {
  signal?: AbortSignal;
  onProgress?: (job: ExportPreparation) => void;
}
const preparationPath = (mission: string, job?: string) =>
  `/api/v2/missions/${mission}/export-preparations${job ? `/${job}` : ''}`;

async function prepareMissionExport(
  missionId: string,
  options: ExportOptions = {}
): Promise<ExportPreparation> {
  return (
    await apiClient.post<ExportPreparation>(
      preparationPath(missionId),
      {},
      { signal: options.signal }
    )
  ).data;
}
async function readMissionExportPreparation(
  missionId: string,
  jobId: string,
  options: ExportOptions = {}
): Promise<ExportPreparation> {
  return (
    await apiClient.get<ExportPreparation>(preparationPath(missionId, jobId), {
      signal: options.signal,
    })
  ).data;
}
async function cancelMissionExportPreparation(
  missionId: string,
  jobId: string,
  options: ExportOptions = {}
): Promise<ExportPreparation> {
  return (
    await apiClient.delete<ExportPreparation>(
      preparationPath(missionId, jobId),
      { signal: options.signal, timeout: 5000 }
    )
  ).data;
}
function downloadMetadata(
  blob: Blob,
  headers: Record<string, unknown> = {}
): MissionExportDownload {
  const status = headers?.['x-customer-briefing-status'];
  const briefingStatus =
    status === 'included' || status === 'omitted' ? status : undefined;
  const warning = headers?.['x-customer-briefing-warning'];
  const warningCode =
    briefingStatus === 'omitted'
      ? typeof warning === 'string' && briefingWarnings.has(warning)
        ? warning
        : 'runtime'
      : undefined;
  return { blob: blob, briefingStatus, warningCode };
}

async function downloadPreparedMissionExport(
  missionId: string,
  jobId: string,
  options: ExportOptions = {}
): Promise<MissionExportDownload> {
  const response = await apiClient.get<Blob>(
    `${preparationPath(missionId, jobId)}/download`,
    { responseType: 'blob', signal: options.signal }
  );
  return downloadMetadata(response.data, response.headers);
}
function pollDelay(signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', abort);
      resolve();
    }, 500);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
  });
}
async function exportMissionDownload(
  missionId: string,
  options: ExportOptions = {}
): Promise<MissionExportDownload> {
  const response = await apiClient.post<Blob | ExportPreparation>(
    `/api/v2/missions/${missionId}/export`,
    {},
    { responseType: 'blob', signal: options.signal }
  );
  if (response.status !== 202)
    return downloadMetadata(response.data as Blob, response.headers);
  let job =
    response.data instanceof Blob
      ? (JSON.parse(await response.data.text()) as ExportPreparation)
      : response.data;
  let terminal = false;
  try {
    options.onProgress?.(job);
    while (job.state !== 'ready') {
      if (
        ['failed', 'cancelled', 'superseded', 'expired'].includes(job.state)
      ) {
        terminal = true;
        throw new Error(
          job.error_code === 'deadline'
            ? 'Preparation reached its time limit. Please retry.'
            : job.state === 'superseded'
              ? 'The mission changed during preparation. Export again to use the latest changes.'
              : 'Export preparation failed. Please retry.'
        );
      }
      job = await readMissionExportPreparation(missionId, job.id, options);
      options.onProgress?.(job);
      if (job.state === 'queued' || job.state === 'preparing')
        await pollDelay(options.signal);
    }
    terminal = true;
    return await downloadPreparedMissionExport(missionId, job.id, options);
  } finally {
    if (!terminal)
      await cancelMissionExportPreparation(missionId, job.id).catch(() => {});
  }
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
  prepareMissionExport,
  readMissionExportPreparation,
  cancelMissionExportPreparation,
  downloadPreparedMissionExport,
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
