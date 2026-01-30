import { useState } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '../components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Step options
const STEP_OPTIONS = [
  { value: 'auto', label: 'Auto' },
  { value: '1', label: '1 second' },
  { value: '10', label: '10 seconds' },
  { value: '60', label: '1 minute' },
  { value: '300', label: '5 minutes' },
];

// Helper to format datetime-local value in Zulu (UTC)
function formatDateTimeLocalUTC(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

// Get default start time (24 hours ago) in Zulu
function getDefaultStart(): string {
  const date = new Date();
  date.setUTCHours(date.getUTCHours() - 24);
  return formatDateTimeLocalUTC(date);
}

// Get default end time (now) in Zulu
function getDefaultEnd(): string {
  return formatDateTimeLocalUTC(new Date());
}

// Convert datetime-local value (treated as Zulu) to ISO string
function toZuluISO(datetimeLocal: string): string {
  // datetime-local gives us "YYYY-MM-DDTHH:MM", treat as UTC
  return datetimeLocal + ':00.000Z';
}

export function DataExportPage() {
  const [startTime, setStartTime] = useState(getDefaultStart());
  const [endTime, setEndTime] = useState(getDefaultEnd());
  const [step, setStep] = useState('auto');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setError(null);
    setIsExporting(true);

    try {
      // Convert to ISO 8601 (input is already Zulu)
      const startISO = toZuluISO(startTime);
      const endISO = toZuluISO(endTime);

      // Build URL
      const params = new URLSearchParams({
        start: startISO,
        end: endISO,
      });

      if (step !== 'auto') {
        params.set('step', step);
      }

      const url = `${API_BASE_URL}/api/export/starlink-csv?${params.toString()}`;

      // Fetch the CSV
      const response = await fetch(url);

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Export failed: ${response.statusText}`);
      }

      // Get filename from Content-Disposition header or generate one
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'starlink-export.csv';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+)"/);
        if (match) {
          filename = match[1];
        }
      }

      // Download the file
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  // Validate that start is before end
  const isValid =
    startTime && endTime && new Date(startTime) < new Date(endTime);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Data Export</h1>
        <p className="text-gray-600 mt-2">
          Export historical Starlink telemetry data to CSV
        </p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Export Settings</CardTitle>
          <CardDescription>
            Select a date/time range (Zulu) and resolution for your export
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Start Time */}
          <div className="space-y-2">
            <Label htmlFor="start-time">Start Time (Z)</Label>
            <Input
              id="start-time"
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </div>

          {/* End Time */}
          <div className="space-y-2">
            <Label htmlFor="end-time">End Time (Z)</Label>
            <Input
              id="end-time"
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </div>

          {/* Step Interval */}
          <div className="space-y-2">
            <Label htmlFor="step">Resolution</Label>
            <Select value={step} onValueChange={setStep}>
              <SelectTrigger id="step">
                <SelectValue placeholder="Select resolution" />
              </SelectTrigger>
              <SelectContent>
                {STEP_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-gray-500">
              Auto adjusts based on time range (1s for short ranges, 5min for
              long ranges)
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Export Button */}
          <Button
            onClick={handleExport}
            disabled={!isValid || isExporting}
            className="w-full"
          >
            {isExporting ? 'Exporting...' : 'Export CSV'}
          </Button>

          {!isValid && startTime && endTime && (
            <p className="text-sm text-red-600">
              Start time must be before end time
            </p>
          )}
        </CardContent>
      </Card>

      {/* Info section */}
      <Card className="max-w-xl mt-6">
        <CardHeader>
          <CardTitle>Exported Data</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-3">
            The CSV export includes the following metrics:
          </p>
          <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
            <li>Position: latitude, longitude, altitude, speed, heading</li>
            <li>Network: latency, throughput (up/down), packet loss</li>
            <li>Signal: obstruction percent, signal quality</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
