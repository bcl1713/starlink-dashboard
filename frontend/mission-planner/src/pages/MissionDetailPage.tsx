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
import { useMission, useAddLeg, useDeleteLeg } from '../hooks/api/useMissions';
import { AddLegDialog } from '../components/missions/AddLegDialog';
import type { MissionLeg } from '../types/mission';

export function MissionDetailPage() {
  const { missionId } = useParams<{ missionId: string }>();
  const navigate = useNavigate();
  const [showAddLegDialog, setShowAddLegDialog] = useState(false);
  const { data: mission, isLoading, error } = useMission(missionId || '');
  const addLegMutation = useAddLeg(missionId || '');
  const deleteLegMutation = useDeleteLeg(missionId || '');

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

  const handleDeleteLeg = (legId: string) => {
    if (window.confirm('Are you sure you want to delete this leg?')) {
      deleteLegMutation.mutate(legId);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{mission.name}</h1>
          <p className="text-muted-foreground mt-2">{mission.description}</p>
          <p className="text-sm text-gray-500 mt-2">ID: {mission.id}</p>
        </div>
        <Button variant="outline" onClick={() => navigate('/missions')}>
          Back to Missions
        </Button>
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
              <Card key={leg.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div
                      className="flex-1 cursor-pointer"
                      onClick={() =>
                        navigate(`/missions/${mission.id}/legs/${leg.id}`)
                      }
                    >
                      <CardTitle>{leg.name}</CardTitle>
                      {leg.description && (
                        <CardDescription>{leg.description}</CardDescription>
                      )}
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteLeg(leg.id)}
                      disabled={deleteLegMutation.isPending}
                      className="ml-2"
                    >
                      {deleteLegMutation.isPending ? 'Deleting...' : 'Delete'}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div
                    className="cursor-pointer"
                    onClick={() =>
                      navigate(`/missions/${mission.id}/legs/${leg.id}`)
                    }
                  >
                    <p className="text-sm text-gray-600">ID: {leg.id}</p>
                    {leg.route_id && (
                      <p className="text-sm text-gray-600 mt-1">
                        Route: {leg.route_id}
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-2">
                      Click to configure leg
                    </p>
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
        onAddLeg={handleAddLeg}
        isSubmitting={addLegMutation.isPending}
      />
    </div>
  );
}
