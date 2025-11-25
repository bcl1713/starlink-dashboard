import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useMission, useAddLeg, useDeleteLeg, useActivateLeg, useDeleteMission } from '../hooks/api/useMissions';
import { AddLegDialog } from '../components/missions/AddLegDialog';
import type { MissionLeg } from '../types/mission';

export function MissionDetailPage() {
  const { missionId } = useParams<{ missionId: string }>();
  const navigate = useNavigate();
  const [showAddLegDialog, setShowAddLegDialog] = useState(false);
  const { data: mission, isLoading, error } = useMission(missionId || '');
  const addLegMutation = useAddLeg(missionId || '');
  const deleteLegMutation = useDeleteLeg(missionId || '');
  const deleteMissionMutation = useDeleteMission();
  const activateLeg = useActivateLeg();

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-muted-foreground">Loading mission...</p>
      </div>
    );
  }

  if (error || !mission) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">
          {error ? 'Error loading mission' : 'Mission not found'}
        </p>
        <Button onClick={() => navigate('/missions')} className="mt-4">
          Back to Missions
        </Button>
      </div>
    );
  }

  const handleAddLeg = async (leg: Partial<MissionLeg>) => {
    await addLegMutation.mutateAsync(leg);
  };

  const handleDeleteMission = async () => {
    const legCount = mission?.legs.length || 0;
    const confirmed = window.confirm(
      `Are you sure you want to delete this mission?\n\n` +
      `This will permanently delete:\n` +
      `- ${legCount} leg(s)\n` +
      `- All associated routes\n` +
      `- All associated POIs\n\n` +
      `This action cannot be undone.`
    );

    if (confirmed) {
      await deleteMissionMutation.mutateAsync(missionId || '');
      navigate('/missions');
    }
  };

  const handleDeleteLeg = (leg: MissionLeg) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete leg "${leg.name}"?\n\n` +
      `This will permanently delete:\n` +
      `- The leg configuration\n` +
      `- Associated route (${leg.route_id || 'none'})\n` +
      `- All associated POIs\n\n` +
      `This action cannot be undone.`
    );

    if (confirmed) {
      deleteLegMutation.mutate(leg.id);
    }
  };

  const handleActivateLeg = (legId: string) => {
    activateLeg.mutate({ missionId: mission!.id, legId });
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{mission.name}</h1>
          <p className="text-muted-foreground mt-2">{mission.description}</p>
          <p className="text-sm text-gray-500 mt-2">ID: {mission.id}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/missions')}>
            Back to Missions
          </Button>
          <Button
            variant="destructive"
            onClick={handleDeleteMission}
            disabled={deleteMissionMutation.isPending}
          >
            {deleteMissionMutation.isPending ? 'Deleting...' : 'Delete Mission'}
          </Button>
        </div>
      </div>

      <div className="border-t pt-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-semibold">Mission Legs</h2>
          <Button
            onClick={() => setShowAddLegDialog(true)}
            disabled={addLegMutation.isPending}
          >
            Add Leg
          </Button>
        </div>
        {mission.legs.length === 0 ? (
          <p className="text-muted-foreground">No legs configured for this mission</p>
        ) : (
          <div className="grid gap-4">
            {mission.legs.map((leg) => (
              <Card
                key={leg.id}
                className={`hover:shadow-lg transition-shadow cursor-pointer ${
                  leg.is_active ? 'border-green-600 border-2' : ''
                }`}
                onClick={() =>
                  navigate(`/missions/${mission.id}/legs/${leg.id}`)
                }
              >
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <CardTitle>{leg.name}</CardTitle>
                        {leg.is_active && (
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-semibold bg-green-600 text-white">
                            Active
                          </span>
                        )}
                      </div>
                      {leg.description && (
                        <CardDescription>{leg.description}</CardDescription>
                      )}
                    </div>
                    <div className="flex gap-2 ml-2">
                      <Button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleActivateLeg(leg.id);
                        }}
                        variant={leg.is_active ? 'default' : 'outline'}
                        size="sm"
                        disabled={activateLeg.isPending}
                      >
                        {activateLeg.isPending
                          ? 'Activating...'
                          : leg.is_active
                            ? 'Active'
                            : 'Activate'}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteLeg(leg);
                        }}
                        disabled={deleteLegMutation.isPending}
                      >
                        {deleteLegMutation.isPending ? 'Deleting...' : 'Delete'}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div>
                    <p className="text-sm text-gray-600">ID: {leg.id}</p>
                    {leg.route_id && (
                      <p className="text-sm text-gray-600 mt-1">
                        Route: {leg.route_id}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <AddLegDialog
        open={showAddLegDialog}
        onOpenChange={setShowAddLegDialog}
        existingLegCount={mission?.legs.length || 0}
        onAddLeg={handleAddLeg}
      />
    </div>
  );
}
