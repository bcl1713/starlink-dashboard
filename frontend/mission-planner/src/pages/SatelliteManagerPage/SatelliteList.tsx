import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import type { SatelliteResponse } from '../../services/satellites';

interface SatelliteListProps {
  satellites: SatelliteResponse[] | undefined;
  isLoading: boolean;
  isDeleting: string | null;
  onEdit: (satellite: SatelliteResponse) => void;
  onDelete: (satelliteId: string) => void;
}

/**
 * Component for displaying the list of satellites
 */
export function SatelliteList({
  satellites,
  isLoading,
  isDeleting,
  onEdit,
  onDelete,
}: SatelliteListProps) {
  if (isLoading) {
    return <p className="mt-4">Loading satellites...</p>;
  }

  if (!satellites || satellites.length === 0) {
    return <p className="mt-4 text-gray-500">No satellites in catalog.</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
      {satellites.map((satellite) => (
        <Card
          key={satellite.satellite_id}
          className="cursor-pointer hover:shadow-lg transition-shadow"
          onClick={() => onEdit(satellite)}
        >
          <CardHeader>
            <CardTitle>{satellite.satellite_id}</CardTitle>
            <CardDescription>
              {satellite.longitude !== null
                ? `${satellite.longitude > 0 ? satellite.longitude + '°E' : Math.abs(satellite.longitude) + '°W'}`
                : 'Position TBD'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm mb-4">
              <p>
                <strong>Transport:</strong> {satellite.transport}-Band
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(satellite.satellite_id);
              }}
              disabled={isDeleting === satellite.satellite_id}
            >
              {isDeleting === satellite.satellite_id ? 'Deleting...' : 'Delete'}
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
