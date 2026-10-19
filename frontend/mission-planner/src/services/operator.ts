import apiClient from './api-client';
import type {
  CommandReceipt,
  HistoryPage,
  OperatorCommand,
  OperatorFailure,
  OperatorHealth,
  ReadRecord,
  RecordFilters,
  RecordPage,
} from '@/types/operator';
const base = '/api/v2/operator';
// api-client wraps Axios errors in Error.cause; keep the structured API boundary.
export function operatorFailure(error: unknown): OperatorFailure {
  const outer = error as {
    cause?: unknown;
    response?: {
      status?: number;
      data?: { error?: Omit<OperatorFailure, 'status'> };
    };
    message?: string;
  };
  const inner = (outer?.cause ?? outer) as typeof outer;
  return {
    status: inner?.response?.status,
    code: 'network_error',
    message: outer?.message ?? 'Operator request failed',
    retryable: true,
    ...inner?.response?.data?.error,
  };
}
export async function getOperatorHealth(): Promise<OperatorHealth> {
  try {
    return (await apiClient.get<OperatorHealth>(`${base}/health`)).data;
  } catch (error) {
    const outer = error as {
      cause?: unknown;
      response?: { status: number; data: OperatorHealth };
    };
    const response = ((outer?.cause ?? outer) as typeof outer)?.response;
    if (response?.status === 503 && response.data.enabled === true)
      return response.data;
    throw error;
  }
}
export async function provisionOperatorStore(
  health: Pick<OperatorHealth, 'source_mode' | 'simulation_run_id'>
): Promise<OperatorHealth> {
  return (
    await apiClient.post<OperatorHealth>(`${base}/provision`, {
      schema_version: 1,
      expected_source_mode: health.source_mode,
      expected_simulation_run_id: health.simulation_run_id,
    })
  ).data;
}
export async function readOperatorRecords(
  filters: RecordFilters,
  cursor?: string
): Promise<RecordPage> {
  return (
    await apiClient.get<RecordPage>(`${base}/records`, {
      params: { ...filters, cursor },
    })
  ).data;
}
export async function readOperatorRecord(id: string): Promise<ReadRecord> {
  return (
    await apiClient.get<ReadRecord>(`${base}/records/${encodeURIComponent(id)}`)
  ).data;
}
export async function readOperatorHistory(
  id: string,
  cursor?: string
): Promise<HistoryPage> {
  return (
    await apiClient.get<HistoryPage>(
      `${base}/records/${encodeURIComponent(id)}/history`,
      { params: { cursor } }
    )
  ).data;
}
export async function saveOperatorCommand(
  command: OperatorCommand,
  key: string,
  epoch: string,
  replayId?: string | null
): Promise<CommandReceipt> {
  const config = {
    headers: {
      'Idempotency-Key': key,
      'X-Operator-Store-Epoch': epoch,
      ...(replayId ? { 'X-Operator-Replay-Id': replayId } : {}),
    },
  };
  if (command.operation === 'create')
    return (
      await apiClient.post<CommandReceipt>(
        `${base}/records`,
        command.body,
        config
      )
    ).data;
  const path = `${base}/records/${encodeURIComponent(command.record_id)}`;
  if (command.operation === 'update')
    return (await apiClient.put<CommandReceipt>(path, command.body, config))
      .data;
  return (
    await apiClient.post<CommandReceipt>(
      `${path}/${command.operation}`,
      command.body,
      config
    )
  ).data;
}

export async function readOperatingContext() {
  return (
    await apiClient.get<
      import('@/components/operator/workspace/operatingContext').OperatingContext
    >(`${base}/context`)
  ).data;
}
