import { useState } from 'react';
import { Button } from '../components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '../components/ui/card';
import { AddSatelliteDialog } from '../components/satellites/AddSatelliteDialog';
import { useSatellites, useDeleteSatellite } from '../hooks/api/useSatellites';

export default function SatelliteManagerPage() {
  const { data: satellites, isLoading } = useSatellites();
  const deleteSatellite = useDeleteSatellite();
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this satellite?')) {
      deleteSatellite.mutate(id);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Satellite Manager</h1>
      <Button onClick={() => setShowCreateDialog(true)}>Add Satellite</Button>

      {isLoading && <p className="mt-4">Loading satellites...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {satellites?.map((satellite) => (
          <Card key={satellite.id}>
            <CardHeader>
              <CardTitle>{satellite.name}</CardTitle>
              <CardDescription>{satellite.type}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600">{satellite.description}</p>
            </CardContent>
            <CardFooter className="flex gap-2">
              <Button variant="outline" size="sm">
                Edit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleDelete(satellite.id)}
              >
                Delete
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      {showCreateDialog && (
        <AddSatelliteDialog
          open={showCreateDialog}
          onOpenChange={setShowCreateDialog}
        />
      )}
    </div>
  );
}
