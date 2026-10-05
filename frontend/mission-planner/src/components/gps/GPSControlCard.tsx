import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Switch } from '../ui/switch';
import { Satellite, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { gpsService } from '../../services/gps';
import type { GPSConfig, GPSError } from '../../types/gps';

export function GPSControlCard() {
  const [config, setConfig] = useState<GPSConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<GPSError | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setError(null);
      const data = await gpsService.getGPSConfig();
      setConfig(data);
    } catch (err) {
      setError(gpsService.parseError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleToggle = async () => {
    if (!config || updating) return;

    setUpdating(true);
    setError(null);

    try {
      const newConfig = await gpsService.setGPSConfig({
        enabled: !config.enabled,
      });
      setConfig(newConfig);
    } catch (err) {
      setError(gpsService.parseError(err));
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <Card className="w-full">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Satellite className="w-4 h-4" aria-hidden="true" />
            <h2>GPS Configuration</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            role="status"
            aria-label="Loading GPS configuration"
            className="flex items-center justify-center py-4"
          >
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Satellite className="w-4 h-4" aria-hidden="true" />
          <h2>GPS Configuration</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 text-sm text-destructive"
          >
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error.message}</span>
          </div>
        )}

        {config && (
          <>
            <label className="flex min-h-11 items-center justify-between gap-6">
              <span>
                <span className="block text-sm font-medium">
                  Use GPS Location
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  Enable the terminal GPS receiver.
                </span>
              </span>
              <Switch
                aria-label="Use GPS Location"
                checked={config.enabled}
                onChange={() => void handleToggle()}
                disabled={updating || error?.type === 'permission_denied'}
              />
            </label>
            {updating && (
              <p role="status" className="text-sm text-muted-foreground">
                Updating GPS configuration…
              </p>
            )}

            <div className="grid grid-cols-2 gap-4 pt-2 border-t">
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Status</span>
                <div className="flex items-center gap-1.5">
                  {config.ready ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                      <span className="text-sm font-medium text-emerald-400">
                        Ready
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-yellow-500" />
                      <span className="text-sm font-medium text-amber-400">
                        Not Ready
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">
                  Satellites
                </span>
                <div className="flex items-center gap-1.5">
                  <Satellite className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium">
                    {config.satellites}
                  </span>
                </div>
              </div>
            </div>
          </>
        )}

        {!config && !error && (
          <div className="text-sm text-muted-foreground text-center py-2">
            GPS configuration unavailable
          </div>
        )}
      </CardContent>
    </Card>
  );
}
