import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Button } from '../ui/button';
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
            <Satellite className="w-4 h-4" />
            GPS Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Satellite className="w-4 h-4" />
          GPS Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error.message}</span>
          </div>
        )}

        {config && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Use GPS Location</span>
              <Button
                variant={config.enabled ? 'default' : 'outline'}
                size="sm"
                onClick={handleToggle}
                disabled={updating || error?.type === 'permission_denied'}
              >
                {updating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : config.enabled ? (
                  'Enabled'
                ) : (
                  'Disabled'
                )}
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2 border-t">
              <div className="space-y-1">
                <span className="text-xs text-gray-500">Status</span>
                <div className="flex items-center gap-1.5">
                  {config.ready ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                      <span className="text-sm font-medium text-green-700">
                        Ready
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-yellow-500" />
                      <span className="text-sm font-medium text-yellow-700">
                        Not Ready
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs text-gray-500">Satellites</span>
                <div className="flex items-center gap-1.5">
                  <Satellite className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-medium">
                    {config.satellites}
                  </span>
                </div>
              </div>
            </div>
          </>
        )}

        {!config && !error && (
          <div className="text-sm text-gray-500 text-center py-2">
            GPS configuration unavailable
          </div>
        )}
      </CardContent>
    </Card>
  );
}
