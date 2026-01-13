import { useRoute } from '../../hooks/api/useRoutes';
import { RouteMap } from '../common/RouteMap';
import { Card } from '../ui/card';

interface RouteDetailViewProps {
  routeId: string;
}

export function RouteDetailView({ routeId }: RouteDetailViewProps) {
  const { data: route, isLoading, error } = useRoute(routeId);

  if (isLoading) return <div>Loading route details...</div>;
  if (error) return <div>Error loading route: {(error as Error).message}</div>;
  if (!route) return <div>Route not found</div>;

  return (
    <div className="space-y-6">
      <Card>
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-2">{route.name}</h2>
          {route.description && (
            <p className="text-gray-600 mb-4">{route.description}</p>
          )}

          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Waypoints</span>
              <p className="font-semibold">{route.waypoint_count || 0}</p>
            </div>
            <div>
              <span className="text-gray-600">Status</span>
              <p className="font-semibold">
                {route.active ? 'Active' : 'Inactive'}
              </p>
            </div>
            {route.flight_phase && (
              <div>
                <span className="text-gray-600">Flight Phase</span>
                <p className="font-semibold">{route.flight_phase}</p>
              </div>
            )}
          </div>
        </div>
      </Card>

      {route.timing_profile && (
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4">Timing Profile</h3>
            <div className="space-y-2 text-sm">
              {Object.entries(route.timing_profile).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-gray-600 capitalize">
                    {key.replace(/_/g, ' ')}
                  </span>
                  <span className="font-medium">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-4">Route Path</h3>
          <div className="h-96 bg-gray-100 rounded">
            {route.points && route.points.length > 0 && (
              <RouteMap
                coordinates={route.points.map((p) => [p.latitude, p.longitude])}
              />
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
