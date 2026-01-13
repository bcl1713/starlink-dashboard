import { useRoutes, useDeleteRoute } from '../../hooks/api/useRoutes';
import type { Route } from '../../services/routes';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Button } from '../ui/button';
import { Trash2, Download, Eye } from 'lucide-react';

interface RouteListProps {
  onSelectRoute: (id: string) => void;
  onDelete: (id: string) => void;
  onDownload: (route: Route) => void;
}

export function RouteList({
  onSelectRoute,
  onDelete,
  onDownload,
}: RouteListProps) {
  const { data: routes, isLoading, error } = useRoutes();
  const deleteRoute = useDeleteRoute();

  if (isLoading) return <div>Loading routes...</div>;
  if (error) return <div>Error loading routes: {(error as Error).message}</div>;

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this route?')) {
      deleteRoute.mutate(id);
      onDelete(id);
    }
  };

  return (
    <div className="border rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Waypoints</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {routes?.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                No routes yet. Upload a route to get started.
              </TableCell>
            </TableRow>
          ) : (
            routes?.map((route) => (
              <TableRow key={route.id}>
                <TableCell className="font-medium">{route.name}</TableCell>
                <TableCell>{route.waypoint_count || 0}</TableCell>
                <TableCell>
                  <span
                    className={`px-2 py-1 rounded-full text-sm ${
                      route.active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {route.active ? 'Active' : 'Inactive'}
                  </span>
                </TableCell>
                <TableCell>
                  {route.created_at
                    ? new Date(route.created_at).toLocaleDateString()
                    : '-'}
                </TableCell>
                <TableCell className="text-right space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onSelectRoute(route.id)}
                  >
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDownload(route)}
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(route.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
