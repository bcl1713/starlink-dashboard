import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { exportImportApi } from '../../services/export-import';
import type { ExportProgress } from '../../types/export';

interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  missionId: string;
  missionName: string;
}

export function ExportDialog({
  open,
  onClose,
  missionId,
  missionName,
}: ExportDialogProps) {
  const [progress, setProgress] = useState<ExportProgress>({
    status: 'preparing',
    message: 'Preparing export...',
  });

  const handleExport = async () => {
    try {
      setProgress({
        status: 'exporting',
        message: 'Exporting mission...',
        progress: 50,
      });

      const blob = await exportImportApi.exportMission(missionId);

      // Trigger download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${missionId}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setProgress({
        status: 'complete',
        message: 'Export complete!',
        progress: 100,
      });

      setTimeout(() => {
        onClose();
        setProgress({ status: 'preparing', message: 'Preparing export...' });
      }, 2000);
    } catch (error) {
      setProgress({
        status: 'error',
        message: `Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export Mission: {missionName}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Export will include all legs, routes, POIs, and pre-generated
            documents.
          </p>

          {progress.status !== 'preparing' && (
            <div className="space-y-2">
              <p className="text-sm font-medium">{progress.message}</p>
              {progress.progress !== undefined && (
                <Progress value={progress.progress} />
              )}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={progress.status === 'exporting'}
            >
              Cancel
            </Button>
            <Button
              onClick={handleExport}
              disabled={
                progress.status === 'exporting' ||
                progress.status === 'complete'
              }
            >
              {progress.status === 'exporting' ? 'Exporting...' : 'Export'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
