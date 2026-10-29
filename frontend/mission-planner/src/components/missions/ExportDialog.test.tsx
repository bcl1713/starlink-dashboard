// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ExportDialog } from './ExportDialog';
import { exportImportApi } from '../../services/export-import';

vi.mock('../../services/export-import', () => ({
  exportImportApi: {
    exportMission: vi.fn(),
    exportMissionDownload: vi.fn(),
  },
}));
const omission =
  'ZIP downloaded. Mission data and CSVs are included; the customer PDF could not be included.';
const props = {
  open: true,
  onClose: vi.fn(),
  missionId: 'm',
  missionName: 'Mission',
};
beforeEach(() => {
  vi.useFakeTimers();
  props.onClose.mockReset();
  vi.mocked(exportImportApi.exportMission).mockResolvedValue(new Blob(['zip']));
  vi.mocked(exportImportApi.exportMissionDownload)
    .mockReset()
    .mockResolvedValue({ blob: new Blob(['zip']) });
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: vi.fn(() => 'blob:download'),
  });
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    value: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});
async function download() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
  });
}

it('lets operators select lossless compact telemetry before exporting', async () => {
  render(<ExportDialog {...props} />);
  fireEvent.change(screen.getByLabelText('Telemetry format'), {
    target: { value: 'compact' },
  });
  await download();
  expect(exportImportApi.exportMissionDownload).toHaveBeenCalledWith(
    'm',
    expect.objectContaining({ telemetryFormat: 'compact' })
  );
});

it('keeps omission feedback and the legacy ZIP visible until dismissal', async () => {
  vi.mocked(exportImportApi.exportMissionDownload).mockResolvedValue({
    blob: new Blob(['zip']),
    briefingStatus: 'omitted',
    warningCode: 'deadline',
  });
  render(<ExportDialog {...props} />);
  await download();
  expect(screen.getByText(omission)).toBeVisible();
  await act(async () => vi.advanceTimersByTime(10000));
  expect(props.onClose).not.toHaveBeenCalled();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:download');
  fireEvent.click(screen.getAllByRole('button', { name: 'Close' })[0]);
  expect(props.onClose).toHaveBeenCalledOnce();
});
it('uses safe generic omission copy for unknown warnings', async () => {
  vi.mocked(exportImportApi.exportMissionDownload).mockResolvedValue({
    blob: new Blob(['zip']),
    briefingStatus: 'omitted',
    warningCode: 'Private renderer traceback',
  });
  render(<ExportDialog {...props} />);
  await download();
  expect(screen.getByText(omission)).toBeVisible();
  expect(screen.queryByText(/Private renderer traceback/)).toBeNull();
});
it('prevents repeated exports while one request is pending', async () => {
  let finish!: (value: { blob: Blob }) => void;
  vi.mocked(exportImportApi.exportMissionDownload).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  render(<ExportDialog {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Export' }));
  fireEvent.click(screen.getByRole('button', { name: 'Exporting...' }));
  expect(exportImportApi.exportMissionDownload).toHaveBeenCalledOnce();
  await act(async () => finish({ blob: new Blob(['zip']) }));
});

it('shows the actual preparation stage and permits cancellation without invented progress', async () => {
  vi.mocked(exportImportApi.exportMissionDownload).mockImplementation(
    async (_mission, options) => {
      options?.onProgress?.({
        id: 'job',
        mission_id: 'm',
        state: 'preparing',
        stage: 'preparing-slides',
        fingerprint: 'f',
        leg_states: { a: 'running' },
        queued_at: 0,
        deadline: 600,
      });
      return new Promise(() => {});
    }
  );
  render(<ExportDialog {...props} />);
  await act(async () =>
    fireEvent.click(screen.getByRole('button', { name: 'Export' }))
  );
  expect(screen.getByText(/Preparing customer PDF/)).toBeVisible();
  expect(screen.queryByRole('progressbar')).toBeNull();
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  const signal = vi.mocked(exportImportApi.exportMissionDownload).mock
    .calls[0][1]?.signal;
  expect(signal?.aborted).toBe(true);
  expect(props.onClose).toHaveBeenCalledOnce();
});
it('closes ordinary success after its existing delay and revokes the URL', async () => {
  render(<ExportDialog {...props} />);
  await download();
  expect(screen.getByText('Export complete!')).toBeVisible();
  expect(URL.revokeObjectURL).toHaveBeenCalledOnce();
  await act(async () => vi.advanceTimersByTime(2000));
  expect(props.onClose).toHaveBeenCalledOnce();
});
it('disposes the completion timer on unmount and resets on reopen', async () => {
  const view = render(<ExportDialog {...props} />);
  await download();
  view.rerender(<ExportDialog {...props} open={false} />);
  view.rerender(<ExportDialog {...props} />);
  expect(screen.getByRole('button', { name: 'Export' })).toBeEnabled();
  await act(async () => vi.advanceTimersByTime(3000));
  expect(props.onClose).not.toHaveBeenCalled();
  await download();
  view.unmount();
  await act(async () => vi.advanceTimersByTime(3000));
  expect(props.onClose).not.toHaveBeenCalled();
});
it('keeps a failed download available for retry without creating an object URL', async () => {
  vi.mocked(exportImportApi.exportMissionDownload).mockRejectedValue(
    new Error('Network failure')
  );
  render(<ExportDialog {...props} />);
  await download();
  expect(screen.getByText(/Export failed/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Export' })).toBeEnabled();
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});
it('aborts on dismissal and ignores a late download from the closed dialog', async () => {
  let finish!: (value: { blob: Blob }) => void;
  vi.mocked(exportImportApi.exportMissionDownload).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const view = render(<ExportDialog {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Export' }));
  const signal = vi.mocked(exportImportApi.exportMissionDownload).mock
    .calls[0][1]?.signal;
  view.unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => finish({ blob: new Blob(['zip']) }));
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});
