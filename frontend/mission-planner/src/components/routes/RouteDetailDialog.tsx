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
          <div className="py-8 text-center text-destructive">
            Error loading route: {(error as Error).message}
          </div>
        )}

        {route && (
          <div className="space-y-4">
            {/* Route Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground block">Status</span>
                <span
                  className={`inline-block px-2 py-1 rounded-full text-sm ${
                    route.is_active
                      ? 'status-nominal'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {route.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block">Points</span>
                <p className="font-semibold">{route.point_count || 0}</p>
              </div>
              {route.waypoints && route.waypoints.length > 0 && (
                <div>
                  <span className="text-muted-foreground block">Waypoints</span>
                  <p className="font-semibold">{route.waypoints.length}</p>
                </div>
              )}
              {route.flight_phase && (
                <div>
                  <span className="text-muted-foreground block">
                    Flight Phase
                  </span>
                  <p className="font-semibold">{route.flight_phase}</p>
                </div>
              )}
            </div>

            {route.description && (
              <div>
                <span className="text-muted-foreground text-sm block">
                  Description
                </span>
                <p>{route.description}</p>
              </div>
            )}

            {/* Waypoints List */}
            {route.waypoints && route.waypoints.length > 0 && (
              <div>
                <span className="text-muted-foreground text-sm block mb-2">
                  Waypoints
                </span>
                <div className="flex flex-wrap gap-2">
                  {route.waypoints.map((wp, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 status-advisory rounded text-sm"
                    >
                      {wp.name || `Point ${idx + 1}`}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Map */}
            <div>
              <span className="text-muted-foreground text-sm block mb-2">
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
                  <div className="h-full flex items-center justify-center text-muted-foreground">
                    No route points available
                  </div>
                )}
              </div>
            </div>

            {/* Timing Profile */}
            {route.timing_profile && route.has_timing_data && (
              <div>
                <span className="text-muted-foreground text-sm block mb-2">
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
                        <span className="text-muted-foreground capitalize">
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
