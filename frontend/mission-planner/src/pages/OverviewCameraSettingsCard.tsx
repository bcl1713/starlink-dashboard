import { Switch } from '@/components/ui/switch';
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import {
  setOverviewFollowPreference,
  useOverviewFollowPreference,
} from '@/hooks/useOverviewFollowPreference';
export function OverviewCameraSettingsCard({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  const follow = useOverviewFollowPreference();
  const [failed, setFailed] = useState(false);
  const content = (
    <section aria-label="Overview camera" className="py-4">
      <label className="flex min-h-11 items-center justify-between gap-6 text-sm font-medium">
        <span>
          Follow aircraft on Overview
          <span className="mt-1 block max-w-xl text-sm font-normal text-muted-foreground">
            Follow fresh positions. Manual exploration pauses following;
            recenter to resume. Saved in this browser, off by default.
          </span>
        </span>
        <Switch
          aria-label="Follow aircraft on Overview"
          checked={follow}
          onChange={(event) =>
            setFailed(!setOverviewFollowPreference(event.target.checked))
          }
        />
      </label>
      {failed && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          Unable to save the camera preference in this browser.
        </p>
      )}
    </section>
  );
  return embedded ? content : <Card className="px-6">{content}</Card>;
}
