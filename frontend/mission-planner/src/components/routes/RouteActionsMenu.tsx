import {
  useActivateRoute,
  useDeactivateRoute,
  useDownloadRoute,
} from '../../hooks/api/useRoutes';
import type { Route } from '../../services/routes';
import { Button } from '../ui/button';
import { Download, Power, PowerOff, Trash2 } from 'lucide-react';

interface RouteActionsMenuProps {
  route: Route;
  onDelete: () => void;
  onDownload: (blob: Blob) => void;
}

export function RouteActionsMenu({
  route,
  onDelete,
  onDownload,
}: RouteActionsMenuProps) {
  const activateRoute = useActivateRoute();
  const deactivateRoute = useDeactivateRoute();
  const downloadRoute = useDownloadRoute();

  const handleActivate = () => {
    activateRoute.mutate(route.id);
  };

  const handleDeactivate = () => {
    deactivateRoute.mutate(route.id);
  };

  const handleDownload = () => {
    downloadRoute.mutate(route.id, {
      onSuccess: (blob) => {
        onDownload(blob);
      },
    });
  };

  return (
    <div className="flex gap-2">
      {route.active ? (
        <Button
          variant="outline"
          size="sm"
          onClick={handleDeactivate}
          disabled={deactivateRoute.isPending}
        >
          <PowerOff className="w-4 h-4 mr-2" />
          Deactivate
        </Button>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={handleActivate}
          disabled={activateRoute.isPending}
        >
          <Power className="w-4 h-4 mr-2" />
          Activate
        </Button>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={handleDownload}
        disabled={downloadRoute.isPending}
      >
        <Download className="w-4 h-4 mr-2" />
        Download
      </Button>

      <Button variant="destructive" size="sm" onClick={onDelete}>
        <Trash2 className="w-4 h-4 mr-2" />
        Delete
      </Button>
    </div>
  );
}
