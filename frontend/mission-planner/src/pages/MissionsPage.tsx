import { useState } from 'react';
import { MissionList } from '../components/missions/MissionList';
import { CreateMissionDialog } from '../components/missions/CreateMissionDialog';

export function MissionsPage() {
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const handleSelectMission = (id: string) => {
    console.log('Selected mission:', id);
    // TODO: Navigate to mission detail view
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <MissionList
        onSelectMission={handleSelectMission}
        onCreateNew={() => setCreateDialogOpen(true)}
      />
      <CreateMissionDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
      />
    </div>
  );
}
