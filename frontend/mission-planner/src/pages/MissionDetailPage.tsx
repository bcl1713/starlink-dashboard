import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useMission } from '../hooks/api/useMissions';
import type { Mission } from '../types/mission';

export function MissionDetailPage() {
  const { missionId } = useParams<{ missionId: string }>();
  const navigate = useNavigate();
  const { data: mission, isLoading, error } = useMission(missionId || '');

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
        <h2 className="text-2xl font-semibold mb-4">Mission Legs</h2>
        {mission.legs.length === 0 ? (
          <p className="text-muted-foreground">No legs configured for this mission</p>
        ) : (
          <div className="grid gap-4">
            {mission.legs.map((leg) => (
              <Card
                key={leg.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => navigate(`/missions/${mission.id}/legs/${leg.id}`)}
              >
                <CardHeader>
                  <CardTitle>{leg.name}</CardTitle>
                  {leg.description && (
                    <CardDescription>{leg.description}</CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-600">
                    ID: {leg.id}
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    Click to configure leg
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
