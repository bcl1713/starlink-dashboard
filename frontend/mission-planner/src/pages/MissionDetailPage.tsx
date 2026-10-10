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
import {
  useMission,
  useAddLeg,
  useDeleteLeg,
  useActivateLeg,
  useDeactivateAllLegs,
  useDeleteMission,
  useUpdateMission,
} from '../hooks/api/useMissions';
import { AddLegDialog } from '../components/missions/AddLegDialog';
import { SimulateLegDialog } from '../components/missions/SimulateLegDialog';
import { MissionSimulationStatus } from '../components/missions/MissionSimulationStatus';
import { EditableField } from '../components/missions/EditableField';
import { formatMissionDeletionError } from '../services/mission-deletion';
import type { MissionLeg } from '../types/mission';
import { usePlanning } from '../hooks/api/usePlanning';
import { ExpectedLegCards } from '../components/planning/ExpectedLegCards';

export function MissionDetailPage() {
  const { missionId } = useParams<{ missionId: string }>();
  const navigate = useNavigate();
  const [showAddLegDialog, setShowAddLegDialog] = useState(false);
  const [simulationLegId, setSimulationLegId] = useState<string | null>(null);
  const { data: mission, isLoading, error } = useMission(missionId || '');
  const planning = usePlanning(
    missionId || '',
    !!mission?.metadata?.itinerary_planning
  );
  const addLegMutation = useAddLeg(missionId || '');
  const deleteLegMutation = useDeleteLeg(missionId || '');
  const deleteMissionMutation = useDeleteMission();
  const updateMissionMutation = useUpdateMission();
  const activateLeg = useActivateLeg();
  const deactivateAllLegs = useDeactivateAllLegs(missionId || '');

  if (isLoading) {
    return (
      <div className="app-page">
        <p className="text-muted-foreground">Loading mission...</p>
      </div>
    );
  }

  if (error || !mission) {
    return (
      <div className="app-page">
        <p className="text-destructive">
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

  const handleDeleteMission = async (confirmed: boolean) => {
    if (confirmed) {
      try {
        await deleteMissionMutation.mutateAsync(missionId || '');
        navigate('/missions');
      } catch (error) {
        console.error('Failed to delete mission:', error);
        alert(formatMissionDeletionError(error));
      }
    }
  };

  const handleDeleteLeg = async (leg: MissionLeg, confirmed: boolean) => {
    if (confirmed) {
      try {
        await deleteLegMutation.mutateAsync(leg.id);
      } catch (error) {
        console.error('Failed to delete leg:', error);
        alert(formatMissionDeletionError(error));
      }
    }
  };

  const handleActivateLeg = (legId: string) => {
    activateLeg.mutate({ missionId: mission!.id, legId });
  };

  const handleDeactivateAllLegs = () => {
    const confirmed = window.confirm('Deactivate all legs?');
    if (confirmed) {
      deactivateAllLegs.mutate();
    }
  };

  const handleUpdateName = async (newName: string) => {
    await updateMissionMutation.mutateAsync({
      id: mission!.id,
      updates: { name: newName },
    });
  };

  const handleUpdateDescription = async (newDescription: string) => {
    await updateMissionMutation.mutateAsync({
      id: mission!.id,
      updates: { description: newDescription },
    });
  };

  const renderInstalledActions = (legId: string) => {
    const leg = mission.legs.find((leg) => leg.id === legId);
    if (!leg) return null;
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSimulationLegId(leg.id)}
        >
          Simulate leg…
        </Button>
        <Button
          variant={leg.is_active ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleActivateLeg(leg.id)}
          disabled={activateLeg.isPending}
        >
          {activateLeg.isPending
            ? 'Activating...'
            : leg.is_active
              ? 'Active'
              : 'Activate'}
        </Button>
      </div>
    );
  };

  return (
    <div className="app-page space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start">
        <div className="min-w-0 flex-1">
          <EditableField
            value={mission.name}
            onSave={handleUpdateName}
            isLoading={updateMissionMutation.isPending}
            placeholder="Mission name"
            className="page-title"
          />
          <EditableField
            value={mission.description || 'No description'}
            onSave={handleUpdateDescription}
            isLoading={updateMissionMutation.isPending}
            placeholder="Mission description"
            multiline
            className="text-muted-foreground mt-2"
          />
          <p className="text-sm text-muted-foreground mt-2">ID: {mission.id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => navigate('/missions')}>
            Back to Missions
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
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
                handleDeleteMission(confirmed);
              }
            }}
            disabled={deleteMissionMutation.isPending}
          >
            {deleteMissionMutation.isPending ? 'Deleting...' : 'Delete Mission'}
          </Button>
        </div>
      </div>

      <MissionSimulationStatus missionId={mission.id} legs={mission.legs} />
      {!!mission.metadata?.itinerary_planning && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold">Itinerary legs</h2>
          {planning.data ? (
            <ExpectedLegCards
              view={planning.data}
              renderInstalledActions={renderInstalledActions}
            />
          ) : (
            <p role={planning.error ? 'alert' : 'status'}>
              {planning.error
                ? 'Unable to load itinerary draft. Reload the mission to retry.'
                : 'Loading itinerary draft…'}
            </p>
          )}
        </div>
      )}
      <div className="border-t pt-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold tracking-tight">
            Mission Legs
          </h2>
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={handleDeactivateAllLegs}
              disabled={
                deactivateAllLegs.isPending || mission.legs.length === 0
              }
              variant="outline"
            >
              {deactivateAllLegs.isPending
                ? 'Deactivating...'
                : 'Deactivate All'}
            </Button>
            <Button
              onClick={() => setShowAddLegDialog(true)}
              disabled={addLegMutation.isPending}
            >
              Add Leg
            </Button>
          </div>
        </div>
        {mission.legs.length === 0 ? (
          <p className="text-muted-foreground">
            No legs configured for this mission
          </p>
        ) : (
          <div className="grid gap-4">
            {mission.legs
              .filter(
                (leg) =>
                  !planning.data?.expected_legs.some(
                    (card) => card.leg.installed_leg_id === leg.id
                  )
              )
              .map((leg) => (
                <Card
                  key={leg.id}
                  className={`hover:shadow-lg transition-shadow cursor-pointer ${
                    leg.is_active
                      ? 'border-[var(--status-nominal)] border-2'
                      : ''
                  }`}
                  onClick={() =>
                    navigate(`/missions/${mission.id}/legs/${leg.id}`)
                  }
                >
                  <CardHeader>
                    <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <CardTitle>{leg.name}</CardTitle>
                          {leg.is_active && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-semibold status-nominal">
                              Active
                            </span>
                          )}
                        </div>
                        {leg.description && (
                          <CardDescription>{leg.description}</CardDescription>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2 ml-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSimulationLegId(leg.id);
                          }}
                        >
                          Simulate leg…
                        </Button>
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
                            const confirmed = window.confirm(
                              `Are you sure you want to delete leg "${leg.name}"?\n\n` +
                                `This will permanently delete:\n` +
                                `- The leg configuration\n` +
                                `- Associated route (${leg.route_id || 'none'})\n` +
                                `- All associated POIs\n\n` +
                                `This action cannot be undone.`
                            );
                            if (confirmed) {
                              handleDeleteLeg(leg, confirmed);
                            }
                          }}
                          disabled={deleteLegMutation.isPending}
                        >
                          {deleteLegMutation.isPending
                            ? 'Deleting...'
                            : 'Delete'}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div>
                      <p className="text-sm text-muted-foreground">
                        ID: {leg.id}
                      </p>
                      {leg.route_id && (
                        <p className="text-sm text-muted-foreground mt-1">
                          Route: {leg.route_id}
                        </p>
                      )}
                      {!planning.data?.expected_legs.some(
                        (card) => card.leg.installed_leg_id === leg.id
                      ) && (
                        <p className="text-sm text-muted-foreground mt-1">
                          Review status not recorded
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
      {simulationLegId && (
        <SimulateLegDialog
          key={simulationLegId}
          missionId={mission.id}
          legId={simulationLegId}
          open
          onOpenChange={(open) => {
            if (!open) setSimulationLegId(null);
          }}
        />
      )}
    </div>
  );
}
