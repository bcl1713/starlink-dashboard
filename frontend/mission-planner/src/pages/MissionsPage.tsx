import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MissionList } from '../components/missions/MissionList';
import { CreateMissionDialog } from '../components/missions/CreateMissionDialog';
import { ExportDialog } from '../components/missions/ExportDialog';
import { ImportDialog } from '../components/missions/ImportDialog';
import { CreateFromItinerary } from '../components/planning/CreateFromItinerary';
import { Button } from '../components/ui/button';

export function MissionsPage() {
  const navigate = useNavigate();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [itineraryOpen, setItineraryOpen] = useState(false);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedMission, setSelectedMission] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const handleSelectMission = () => {
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
    // Optionally navigate to the imported mission
    navigate(`/missions/${missionId}`);
  };

  return (
    <div className="min-h-screen">
      <div className="app-page pb-0">
        <Button onClick={() => setItineraryOpen(true)}>
          Create from itinerary
        </Button>
      </div>
      <MissionList
        onSelectMission={handleSelectMission}
        onCreateNew={() => setCreateDialogOpen(true)}
        onImport={handleImport}
        onExport={handleExport}
      />
      <CreateMissionDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onSuccess={(missionId) => navigate(`/missions/${missionId}`)}
      />
      <CreateFromItinerary
        open={itineraryOpen}
        onClose={() => setItineraryOpen(false)}
        onSuccess={(missionId) => navigate(`/missions/${missionId}`)}
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
