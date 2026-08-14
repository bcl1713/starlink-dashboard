import { useMissions, useDeleteMission } from '../../hooks/api/useMissions';
import { MissionCard } from './MissionCard';
import { Button } from '../ui/button';

interface MissionListProps {
  onSelectMission: (id: string) => void;
  onCreateNew: () => void;
  onImport: () => void;
  onExport: (id: string, name: string) => void;
}

export function MissionList({
  onSelectMission,
  onCreateNew,
  onImport,
  onExport,
}: MissionListProps) {
  const { data: missions, isLoading, error } = useMissions();
  const deleteMission = useDeleteMission();

  if (isLoading)
    return (
      <div className="app-page">
        <div className="rounded-xl border bg-card p-8 text-center text-muted-foreground">
          Loading missions...
        </div>
      </div>
    );
  if (error)
    return (
      <div className="app-page">
        <div className="status-critical rounded-xl border p-4" role="alert">
          Error loading missions: {(error as Error).message}
        </div>
      </div>
    );

  return (
    <div className="app-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Missions</h1>
          <p className="page-description">
            Configure mission legs, route data, and operational communications.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={onImport}>
            Import Mission
          </Button>
          <Button onClick={onCreateNew}>Create New Mission</Button>
        </div>
      </div>

      {missions?.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-card px-6 py-12 text-center text-muted-foreground">
          <p className="font-medium text-foreground">No missions yet</p>
          <p className="mt-1 text-sm">
            Create your first mission to begin planning its route and legs.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {missions?.map((mission) => (
            <MissionCard
              key={mission.id}
              mission={mission}
              onSelect={onSelectMission}
              onDelete={(id) => deleteMission.mutate(id)}
              onExport={onExport}
            />
          ))}
        </div>
      )}
    </div>
  );
}
