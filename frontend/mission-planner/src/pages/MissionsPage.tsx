import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MissionList } from '../components/missions/MissionList';
import { CreateMissionDialog } from '../components/missions/CreateMissionDialog';
import { ExportDialog } from '../components/missions/ExportDialog';
import { ImportDialog } from '../components/missions/ImportDialog';

export function MissionsPage() {
  const navigate = useNavigate();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedMission, setSelectedMission] = useState<{ id: string; name: string } | null>(null);

  const handleSelectMission = (id: string) => {
    console.log('Selected mission:', id);
    // TODO: Navigate to mission detail view
  };

  const handleExport = (id: string, name: string) => {
    setSelectedMission({ id, name });
    setExportDialogOpen(true);
  };

  const handleImport = () => {
    setImportDialogOpen(true);
  };

  const handleImportSuccess = (missionId: string) => {
    console.log('Mission imported:', missionId);
    // Optionally navigate to the imported mission
    navigate(`/missions/${missionId}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <MissionList
        onSelectMission={handleSelectMission}
        onCreateNew={() => setCreateDialogOpen(true)}
        onImport={handleImport}
        onExport={handleExport}
      />
      <CreateMissionDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
      />
      <ExportDialog
        open={exportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
        missionId={selectedMission?.id || ''}
        missionName={selectedMission?.name || ''}
      />
      <ImportDialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        onSuccess={handleImportSuccess}
      />
    </div>
  );
}
