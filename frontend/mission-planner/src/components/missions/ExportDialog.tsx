import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
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
  return (
    <Dialog open={open} onOpenChange={onClose}>
      {open && (
        <ExportDialogContent
          onClose={onClose}
          missionId={missionId}
          missionName={missionName}
        />
      )}
    </Dialog>
  );
}

function ExportDialogContent({
  onClose,
  missionId,
  missionName,
}: Omit<ExportDialogProps, 'open'>) {
  const [warnings, setWarnings] = useState<string[]>([]);
  const [progress, setProgress] = useState<ExportProgress>({
    status: 'preparing',
    message: 'Preparing export...',
  });

  useEffect(() => {
    if (progress.status !== 'complete' || warnings.length > 0) return;
    const timer = window.setTimeout(onClose, 2000);
    return () => window.clearTimeout(timer);
  }, [progress.status, warnings.length, onClose]);

  const handleExport = async () => {
    try {
      setProgress({
        status: 'exporting',
        message: 'Exporting mission...',
        progress: 50,
      });

      const { blob, warnings: exportWarnings } =
        await exportImportApi.exportMissionResult(missionId);

      // Trigger download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${missionId}.zip`;
      document.body.appendChild(a);
      try {
        a.click();
      } finally {
        window.URL.revokeObjectURL(url);
        a.remove();
      }
      setWarnings(exportWarnings);

      setProgress({
        status: 'complete',
        message:
          exportWarnings.length > 0
            ? 'Export downloaded with warnings.'
            : 'Export complete!',
        progress: 100,
      });
    } catch (error) {
      setProgress({
        status: 'error',
        message: `Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
    }
  };

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Export Mission: {missionName}</DialogTitle>
        <DialogDescription>
          Export includes all legs, routes, POIs, and mission documents.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        {progress.status !== 'preparing' && (
          <div className="space-y-2">
            <p className="text-sm font-medium">{progress.message}</p>
            {progress.progress !== undefined && (
              <Progress value={progress.progress} />
            )}
          </div>
        )}

        {warnings.length > 0 && (
          <div role="alert" className="space-y-2 text-sm">
            <p className="font-medium">Export warnings</p>
            <ul className="list-disc space-y-1 pl-5">
              {warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={progress.status === 'exporting'}
          >
            {progress.status === 'complete' ? 'Close' : 'Cancel'}
          </Button>
          <Button
            onClick={handleExport}
            disabled={
              progress.status === 'exporting' || progress.status === 'complete'
            }
          >
            {progress.status === 'exporting' ? 'Exporting...' : 'Export'}
          </Button>
        </div>
      </div>
    </DialogContent>
  );
}
