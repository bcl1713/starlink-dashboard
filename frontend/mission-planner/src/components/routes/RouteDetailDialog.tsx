import { useRoute } from '../../hooks/api/useRoutes';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { RouteMap } from '../common/RouteMap';

interface RouteDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  routeId: string | null;
}

export function RouteDetailDialog({
  open,
  onOpenChange,
  routeId,
}: RouteDetailDialogProps) {
  const { data: route, isLoading, error } = useRoute(routeId || '');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{route?.name || 'Route Details'}</DialogTitle>
        </DialogHeader>

        {isLoading && <div className="py-8 text-center">Loading route...</div>}
        {error && (
          <div className="py-8 text-center text-red-600">
            Error loading route: {(error as Error).message}
          </div>
        )}

        {route && (
          <div className="space-y-4">
            {/* Route Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-600 block">Status</span>
                <span
                  className={`inline-block px-2 py-1 rounded-full text-sm ${
                    route.is_active
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {route.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <div>
                <span className="text-gray-600 block">Points</span>
                <p className="font-semibold">{route.point_count || 0}</p>
              </div>
              {route.waypoints && route.waypoints.length > 0 && (
                <div>
                  <span className="text-gray-600 block">Waypoints</span>
                  <p className="font-semibold">{route.waypoints.length}</p>
                </div>
              )}
              {route.flight_phase && (
                <div>
                  <span className="text-gray-600 block">Flight Phase</span>
                  <p className="font-semibold">{route.flight_phase}</p>
                </div>
              )}
            </div>

            {route.description && (
              <div>
                <span className="text-gray-600 text-sm block">Description</span>
                <p>{route.description}</p>
              </div>
            )}

            {/* Waypoints List */}
            {route.waypoints && route.waypoints.length > 0 && (
              <div>
                <span className="text-gray-600 text-sm block mb-2">
                  Waypoints
                </span>
                <div className="flex flex-wrap gap-2">
                  {route.waypoints.map((wp, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm"
                    >
                      {wp.name || `Point ${idx + 1}`}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Map */}
            <div>
              <span className="text-gray-600 text-sm block mb-2">
                Route Path
              </span>
              <div className="h-80 border rounded-lg overflow-hidden">
                {route.points && route.points.length > 0 ? (
                  <RouteMap
                    coordinates={route.points.map((p) => [
                      p.latitude,
                      p.longitude,
                    ])}
                  />
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    No route points available
                  </div>
                )}
              </div>
            </div>

            {/* Timing Profile */}
            {route.timing_profile && route.has_timing_data && (
              <div>
                <span className="text-gray-600 text-sm block mb-2">
                  Timing Profile
                </span>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {Object.entries(route.timing_profile)
                    .filter(
                      ([key]) =>
                        !key.startsWith('_') && key !== 'has_timing_data'
                    )
                    .map(([key, value]) => (
                      <div key={key} className="flex justify-between">
                        <span className="text-gray-600 capitalize">
                          {key.replace(/_/g, ' ')}
                        </span>
                        <span className="font-medium">
                          {typeof value === 'object'
                            ? JSON.stringify(value)
                            : String(value)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
