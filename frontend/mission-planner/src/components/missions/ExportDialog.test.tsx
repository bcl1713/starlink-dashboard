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
  'ZIP downloaded. Legacy documents are included; the customer PDF could not be included.';
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
