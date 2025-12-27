import { useRef } from 'react';
import { Button } from '../../components/ui/button';
import { useUpdateLegRoute } from '../../hooks/api/useMissions';

interface LegHeaderProps {
  missionId: string;
  legId: string;
  routeId?: string;
  onBackClick: () => void;
}

/**
 * Header component for the Leg Detail page
 */
export function LegHeader({
  missionId,
  legId,
  routeId,
  onBackClick,
}: LegHeaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const updateRouteMutation = useUpdateLegRoute(missionId);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.kml')) {
        alert('Please select a .kml file');
        return;
      }
      handleUpload(file);
    }
  };

  const handleUpload = async (file: File) => {
    try {
      const result = await updateRouteMutation.mutateAsync({ legId, file });

      if (result.warnings && result.warnings.length > 0) {
        alert(
          `Route updated successfully!\n\nWarnings:\n${result.warnings.join('\n')}`
        );
      } else {
        alert('Route updated successfully!');
      }

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Failed to update route:', error);
      alert('Failed to update route. Please try again.');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleUpdateRouteClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div>
      <Button variant="ghost" onClick={onBackClick} className="mb-4">
        ← Back to Mission
      </Button>
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">Leg Configuration</h1>
          <p className="text-muted-foreground">
            Mission: {missionId} | Leg: {legId}
          </p>
          {routeId && (
            <p className="text-sm text-muted-foreground mt-1">
              Current route: {routeId}
            </p>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".kml"
            onChange={handleFileSelect}
            className="hidden"
          />
          <Button
            variant="outline"
            onClick={handleUpdateRouteClick}
            disabled={updateRouteMutation.isPending}
          >
            {updateRouteMutation.isPending ? 'Uploading...' : 'Update Route'}
          </Button>
        </div>
      </div>
    </div>
  );
}
