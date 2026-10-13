import { useEffect, useRef, useState } from 'react';
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

export function ExportDialog(props: ExportDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onClose}>
      {props.open && <ExportContent key={props.missionId} {...props} />}
    </Dialog>
  );
}

function ExportContent({ onClose, missionId, missionName }: ExportDialogProps) {
  const mounted = useRef(true);
  const busy = useRef(false);
  const request = useRef<AbortController | null>(null);
  const completionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [briefingOmitted, setBriefingOmitted] = useState(false);
  const [progress, setProgress] = useState<ExportProgress>({
    status: 'preparing',
    message: 'Preparing export...',
  });

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
      if (completionTimer.current !== null)
        clearTimeout(completionTimer.current);
    };
  }, []);

  const handleExport = async () => {
    if (busy.current) return;
    busy.current = true;
    request.current = new AbortController();
    try {
      setProgress({
        status: 'exporting',
        message: 'Preparing export...',
      });

      const download = await exportImportApi.exportMissionDownload(missionId, {
        signal: request.current.signal,
        onProgress: (job) => {
          if (!mounted.current) return;
          const stages: Record<string, string> = {
            queued: 'Export queued...',
            'preparing-slides': 'Preparing customer PDF...',
            assembling: 'Assembling mission ZIP...',
            ready: 'Downloading mission ZIP...',
          };
          setProgress({
            status: 'exporting',
            message: stages[job.stage] ?? 'Preparing export...',
          });
        },
      });
      if (!mounted.current) return;

      // Trigger download
      const url = window.URL.createObjectURL(download.blob);
      const a = document.createElement('a');
      try {
        a.href = url;
        a.download = `${missionId}.zip`;
        document.body.appendChild(a);
        a.click();
      } finally {
        window.URL.revokeObjectURL(url);
        a.remove();
      }

      const omitted = download.briefingStatus === 'omitted';
      setBriefingOmitted(omitted);
      setProgress({
        status: 'complete',
        message: omitted
          ? 'ZIP downloaded. Mission data and CSVs are included; the customer PDF could not be included.'
          : 'Export complete!',
        progress: 100,
      });

      if (!omitted)
        completionTimer.current = setTimeout(() => {
          if (mounted.current) onClose();
        }, 2000);
    } catch (error) {
      if (!mounted.current || request.current?.signal.aborted) return;
      setProgress({
        status: 'error',
        message:
          error instanceof Error &&
          /^(Preparation reached|The mission changed|Export preparation failed)/.test(
            error.message
          )
            ? error.message
            : 'Export failed. Please try again.',
      });
    } finally {
      busy.current = false;
    }
  };

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Export Mission: {missionName}</DialogTitle>
      </DialogHeader>

      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Export will include all legs, routes, POIs, CSVs, and the customer
          PDF. PDF pages prepare automatically after saved changes.
        </p>

        {progress.status !== 'preparing' && (
          <div className="space-y-2">
            <p className="text-sm font-medium">{progress.message}</p>
            {progress.status === 'complete' && briefingOmitted && (
              <p className="text-sm text-muted-foreground">
                You can retry the export. If this continues, contact support.
              </p>
            )}
            {progress.progress !== undefined && (
              <Progress value={progress.progress} />
            )}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              request.current?.abort();
              onClose();
            }}
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
