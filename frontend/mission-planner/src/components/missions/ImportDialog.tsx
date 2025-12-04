import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { exportImportApi } from '../../services/export-import';
import type { ImportResult } from '../../types/export';

interface ImportDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (missionId: string) => void;
}

export function ImportDialog({ open, onClose, onSuccess }: ImportDialogProps) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setUploading(true);
    setResult(null);

    try {
      const importResult = await exportImportApi.importMission(file);
      setResult(importResult);

      if (importResult.success && importResult.mission_id) {
        setTimeout(() => {
          onSuccess(importResult.mission_id!);
          onClose();
          setResult(null);
        }, 2000);
      }
    } catch (error) {
      setResult({
        success: false,
        errors: [
          {
            field: 'general',
            message: error instanceof Error ? error.message : 'Unknown error',
          },
        ],
      });
    } finally {
      setUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/zip': ['.zip'],
    },
    multiple: false,
    disabled: uploading,
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import Mission</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input {...getInputProps()} />
            {uploading ? (
              <p className="text-gray-600">Uploading and validating...</p>
            ) : isDragActive ? (
              <p className="text-blue-600">Drop the zip file here...</p>
            ) : (
              <div>
                <p className="text-gray-600">
                  Drag and drop a mission zip file here, or click to select
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  Only .zip files are accepted
                </p>
              </div>
            )}
          </div>

          {result && (
            <div
              className={`p-4 rounded-md ${
                result.success
                  ? 'bg-green-50 text-green-800'
                  : 'bg-red-50 text-red-800'
              }`}
            >
              {result.success ? (
                <div>
                  <p className="font-medium">Import successful!</p>
                  <p className="text-sm mt-1">
                    Mission ID: {result.mission_id}
                  </p>
                  {result.warnings && result.warnings.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm font-medium">Warnings:</p>
                      <ul className="list-disc list-inside text-sm">
                        {result.warnings.map((warning, i) => (
                          <li key={i}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <p className="font-medium">Import failed</p>
                  {result.errors && (
                    <ul className="list-disc list-inside text-sm mt-1">
                      {result.errors.map((error, i) => (
                        <li key={i}>
                          {error.field}: {error.message}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end">
            <Button variant="outline" onClick={onClose} disabled={uploading}>
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
