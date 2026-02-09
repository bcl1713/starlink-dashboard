import { GPSControlCard } from '../components/gps/GPSControlCard';

export function ConfigurationPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Configuration</h1>
      </div>

      <div className="max-w-xl">
        <GPSControlCard />
      </div>
    </div>
  );
}
