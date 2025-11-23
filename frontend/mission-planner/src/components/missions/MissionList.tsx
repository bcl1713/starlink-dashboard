import { useMissions, useDeleteMission } from '../../hooks/api/useMissions';
import { MissionCard } from './MissionCard';
import { Button } from '../ui/button';

interface MissionListProps {
  onSelectMission: (id: string) => void;
  onCreateNew: () => void;
}

export function MissionList({ onSelectMission, onCreateNew }: MissionListProps) {
  const { data: missions, isLoading, error } = useMissions();
  const deleteMission = useDeleteMission();

  if (isLoading) return <div>Loading missions...</div>;
  if (error) return <div>Error loading missions: {(error as Error).message}</div>;

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Missions</h1>
        <Button onClick={onCreateNew}>Create New Mission</Button>
      </div>

      {missions?.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No missions yet. Create your first mission to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {missions?.map((mission) => (
            <MissionCard
              key={mission.id}
              mission={mission}
              onSelect={onSelectMission}
              onDelete={(id) => deleteMission.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
