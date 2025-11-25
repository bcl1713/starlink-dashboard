import { useSatellites } from '../hooks/api/useSatellites';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '../components/ui/card';

export default function SatelliteManagerPage() {
  const { data: satellites, isLoading } = useSatellites();

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">X-Band Satellite Catalog</h1>
        <p className="text-gray-600">
          X-Band satellites loaded from the system catalog. These are geostationary satellites at the equator.
        </p>
      </div>

      {isLoading && <p className="mt-4">Loading satellites...</p>}

      {!isLoading && satellites && satellites.length === 0 && (
        <p className="mt-4 text-gray-500">No satellites in catalog.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {satellites?.map((satellite) => (
          <Card key={satellite.satellite_id}>
            <CardHeader>
              <CardTitle>{satellite.satellite_id}</CardTitle>
              <CardDescription>
                {satellite.longitude !== null
                  ? `${satellite.longitude > 0 ? satellite.longitude + '°E' : Math.abs(satellite.longitude) + '°W'}`
                  : 'Position TBD'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <p><strong>Transport:</strong> {satellite.transport}-Band</p>
                {satellite.slot && <p><strong>Slot:</strong> {satellite.slot}</p>}
                <div className="flex items-center gap-2 mt-2">
                  <div
                    className="w-6 h-6 rounded-full border border-gray-300"
                    style={{ backgroundColor: satellite.color }}
                  />
                  <span className="text-xs text-gray-500">Display color</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
