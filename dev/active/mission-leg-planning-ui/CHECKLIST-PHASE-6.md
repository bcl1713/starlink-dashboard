# Checklist: Phase 6 - Export/Import UI & Integration

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Phase:** 6 - Export/Import UI & Integration
**Status:** Not Started

> This checklist covers building the export dialog for downloading mission packages and import interface for uploading zips, integrated with backend endpoints.

---

## Phase 6 Overview

**Goal:** Build export dialog allowing users to download mission packages, and import interface for uploading zips. Integrate with backend endpoints.

**Exit Criteria:**
- Export dialog triggers zip download with progress indicator
- Import drag-and-drop interface accepts zip files
- Import validation displays clear error messages
- Successful import recreates mission with all legs, routes, POIs
- Export package tested on separate system instance

---

## 6.1: Add Export/Import API Types

### 6.1.1: Create export/import types

- [x] Create `frontend/mission-planner/src/types/export.ts`
- [x] Add export/import interfaces:
  ```typescript
  export interface ExportProgress {
    status: 'preparing' | 'exporting' | 'complete' | 'error';
    message: string;
    progress?: number;
  }

  export interface ImportValidationError {
    field: string;
    message: string;
  }

  export interface ImportResult {
    success: boolean;
    mission_id?: string;
    errors?: ImportValidationError[];
    warnings?: string[];
  }
  ```
- [x] Save file (verify < 350 lines)
- [x] Expected: Type definitions for export/import operations

---

## 6.2: Create Export/Import API Service

### 6.2.1: Implement export/import service

- [x] Create `frontend/mission-planner/src/services/export-import.ts`
- [x] Add export and import functions:
  ```typescript
  import { apiClient } from './api-client';
  import type { ImportResult } from '../types/export';

  export const exportImportApi = {
    exportMission: async (missionId: string): Promise<Blob> => {
      const response = await apiClient.post(
        `/api/v2/missions/${missionId}/export`,
        {},
        {
          responseType: 'blob',
        }
      );
      return response.data;
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
  ```
- [x] Save file (verify < 350 lines)
- [x] Expected: Export/import API service functions

---

## 6.3: Create Export Dialog Component

### 6.3.1: Install additional UI components

- [x] Install Progress component:
  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add progress
  ```
- [x] Expected: Progress component available

### 6.3.2: Create ExportDialog component

- [x] Create `frontend/mission-planner/src/components/missions/ExportDialog.tsx`
- [x] Implement export dialog with progress indicator:
  ```typescript
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
        setProgress({ status: 'exporting', message: 'Exporting mission...', progress: 50 });

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

        setProgress({ status: 'complete', message: 'Export complete!', progress: 100 });

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
              Export will include all legs, routes, POIs, and pre-generated documents.
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
              <Button variant="outline" onClick={onClose} disabled={progress.status === 'exporting'}>
                Cancel
              </Button>
              <Button
                onClick={handleExport}
                disabled={progress.status === 'exporting' || progress.status === 'complete'}
              >
                {progress.status === 'exporting' ? 'Exporting...' : 'Export'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  }
  ```
- [x] Save file (verify < 350 lines)
- [x] Expected: Export dialog with progress tracking

---

## 6.4: Create Import Dialog Component

### 6.4.1: Install drag-and-drop library

- [x] Install react-dropzone:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner install react-dropzone
  ```
- [x] Expected: react-dropzone available

### 6.4.2: Create ImportDialog component

- [x] Create `frontend/mission-planner/src/components/missions/ImportDialog.tsx`
- [x] Implement import dialog with drag-and-drop:
  ```typescript
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
                  <p className="text-sm text-gray-500 mt-2">Only .zip files are accepted</p>
                </div>
              )}
            </div>

            {result && (
              <div
                className={`p-4 rounded-md ${
                  result.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                }`}
              >
                {result.success ? (
                  <div>
                    <p className="font-medium">Import successful!</p>
                    <p className="text-sm mt-1">Mission ID: {result.mission_id}</p>
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
  ```
- [x] Save file (verify < 350 lines)
- [x] Expected: Import dialog with drag-and-drop and validation

---

## 6.5: Integrate Export/Import into Mission UI

### 6.5.1: Add export button to MissionCard

- [x] Open `frontend/mission-planner/src/components/missions/MissionCard.tsx`
- [x] Add export button alongside delete button
- [x] Add onClick handler to trigger export dialog
- [x] Save file (verify < 350 lines)
- [x] Expected: Export button in mission cards

### 6.5.2: Add import button to MissionList

- [ ] Open `frontend/mission-planner/src/components/missions/MissionList.tsx`
- [ ] Add "Import Mission" button next to "Create New Mission"
- [ ] Add state for import dialog
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Import button in mission list header

### 6.5.3: Wire up dialogs in MissionsPage

- [ ] Open `frontend/mission-planner/src/pages/MissionsPage.tsx`
- [ ] Import ExportDialog and ImportDialog components
- [ ] Add state for controlling dialogs
- [ ] Add dialogs to page render
- [ ] Pass callbacks to trigger dialogs from list/cards
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Export and import dialogs functional

---

## 6.6: Backend Integration Testing

### 6.6.1: Verify backend export endpoint

- [ ] Ensure backend is running:
  ```bash
  docker compose ps
  ```
- [ ] Test export endpoint manually:
  ```bash
  curl -X POST http://localhost:8000/api/v2/missions/test-mission-1/export -o test-export.zip
  ```
- [ ] Verify zip file created
- [ ] Expected: Backend export working

### 6.6.2: Add backend import endpoint (if not exists)

- [ ] Check if `/api/v2/missions/import` endpoint exists in backend
- [ ] If not, this needs to be added in Phase 2 revisit
- [ ] Document any missing backend endpoints
- [ ] Expected: Backend import endpoint available

---

## 6.7: End-to-End Testing

### 6.7.1: Test export workflow

- [ ] Start frontend dev server
- [ ] Create a test mission with 2 legs
- [ ] Add routes to legs
- [ ] Configure satellite settings
- [ ] Click "Export" on mission card
- [ ] Verify zip file downloads
- [ ] Inspect zip contents manually
- [ ] Expected: Complete mission package exported

### 6.7.2: Test import workflow

- [ ] Delete the test mission from UI
- [ ] Click "Import Mission" button
- [ ] Drag and drop exported zip file
- [ ] Verify validation messages
- [ ] Verify mission recreated with all data
- [ ] Expected: Mission imported successfully

### 6.7.3: Test validation errors

- [ ] Create an invalid zip file (corrupt or wrong format)
- [ ] Attempt import
- [ ] Verify clear error messages displayed
- [ ] Expected: Validation errors handled gracefully

---

## 6.8: Commit Phase 6 Changes

- [ ] Stage all changes:
  ```bash
  git add frontend/mission-planner/src/
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: implement export/import UI and integration

  - Add export/import API types and service
  - Create ExportDialog with progress indicator
  - Create ImportDialog with drag-and-drop
  - Integrate export button into MissionCard
  - Integrate import button into MissionList
  - Add end-to-end export/import workflow
  - Implement validation error display

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6"
  ```
- [ ] Push:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [ ] Expected: Phase 6 committed and pushed

---

## Status

- [ ] All Phase 6 tasks completed
- [ ] Export dialog functional with progress
- [ ] Import dialog functional with validation
- [ ] End-to-end workflow tested
- [ ] Mission packages portable across systems
