import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  setOverviewFollowPreference,
  useOverviewFollowPreference,
} from '@/hooks/useOverviewFollowPreference';
export function OverviewCameraSettingsCard() {
  const follow = useOverviewFollowPreference();
  const [failed, setFailed] = useState(false);
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Overview camera</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex min-h-11 items-center gap-3">
          <input
            type="checkbox"
            checked={follow}
            onChange={(event) =>
              setFailed(!setOverviewFollowPreference(event.target.checked))
            }
          />
          Follow aircraft on Overview
        </label>
        <p className="text-sm text-muted-foreground">
          Off by default. When enabled, the camera follows fresh aircraft
          positions. Manual exploration pauses following; reset the map to
          resume. This preference is saved in this browser.
        </p>
        {failed && (
          <p role="alert">
            Unable to save the camera preference in this browser.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
