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
  const [telemetryFormat, setTelemetryFormat] = useState<'full' | 'compact'>(
    'full'
  );
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
        telemetryFormat,
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
        a.download = `${missionId}${telemetryFormat === 'compact' ? '-compact' : ''}.zip`;
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
          /^(Preparation reached|The mission changed|Export preparation failed|Mission export exceeds|Mission archive capture reached)/.test(
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
        <div className="space-y-2">
          <label
            htmlFor="mission-telemetry-format"
            className="text-sm font-medium"
          >
            Telemetry format
          </label>
          <select
            id="mission-telemetry-format"
            value={telemetryFormat}
            disabled={
              progress.status === 'exporting' || progress.status === 'complete'
            }
            onChange={(event) =>
              setTelemetryFormat(event.target.value as 'full' | 'compact')
            }
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="full">Full detail</option>
            <option value="compact">Compact lossless</option>
          </select>
          <p className="text-sm text-muted-foreground">
            Both retain all recorded observations and complete journal history.
            Compact stores repeated metric and label information in a separate
            series dictionary; no samples are downsampled.
          </p>
        </div>

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
