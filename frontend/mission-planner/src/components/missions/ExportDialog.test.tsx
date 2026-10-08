/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { apiClient } from '../../services/api-client';
import { ExportDialog } from './ExportDialog';

const warning =
  'Customer briefing — Trial could not be generated. Legacy exports are included.';
let downloads: string[];

beforeEach(() => {
  downloads = [];
  vi.stubGlobal(
    'URL',
    class extends URL {
      static createObjectURL = vi.fn(() => 'blob:mission-download');
      static revokeObjectURL = vi.fn();
    }
  );
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(
    function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    }
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function mount(onClose = vi.fn()) {
  return render(
    <ExportDialog open onClose={onClose} missionId="m" missionName="Mission" />
  );
}

it('test_trial_warning_download_result: downloads the legacy ZIP and keeps warnings visible beyond two seconds', async () => {
  vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: new Blob(['zip']),
    headers: {
      'x-mission-export-trial-status': 'failed',
      'x-mission-export-warnings': JSON.stringify([warning]),
    },
  });
  vi.useFakeTimers();
  const onClose = vi.fn();
  mount(onClose);
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
  });
  expect(screen.getByRole('alert')).toHaveTextContent(warning);
  expect(downloads).toEqual(['m.zip']);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mission-download');
  expect(
    screen.queryByText(/customer briefing — trial (included|success)/i)
  ).not.toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2500);
  });
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent(warning);
  fireEvent.click(screen.getAllByRole('button', { name: 'Close' })[0]);
  expect(onClose).toHaveBeenCalledOnce();
});

it('shows an export error without starting a download', async () => {
  vi.spyOn(apiClient, 'post').mockRejectedValue(new Error('Unavailable'));
  mount();
  fireEvent.click(screen.getByRole('button', { name: 'Export' }));
  await screen.findByText('Export failed: Unavailable');
  expect(downloads).toEqual([]);
  expect(screen.getByRole('button', { name: 'Export' })).toBeEnabled();
});

it('resets completed state and old warnings when reopened', async () => {
  vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: new Blob(['zip']),
    headers: { 'x-mission-export-warnings': JSON.stringify([warning]) },
  });
  const props = { onClose: vi.fn(), missionId: 'm', missionName: 'Mission' };
  const view = render(<ExportDialog open {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Export' }));
  await screen.findByRole('alert');
  view.rerender(<ExportDialog open={false} {...props} />);
  view.rerender(<ExportDialog open {...props} />);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Export' })).toBeEnabled();
});
