import { useState } from 'react';
import { useMission, useMissionsPage } from '@/hooks/api/useMissions';

export function MissionContextChooser({
  missionId,
  onChange,
}: {
  missionId: string;
  onChange: (id: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const page = useMissionsPage(50, offset);
  const current = useMission(missionId);
  const missions = page.data?.missions ?? [];
  return (
    <div className="ws-mission-chooser">
      <label>
        Mission
        <select
          className="ws-field"
          value={missionId}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Choose a mission</option>
          {missionId &&
            !missions.some((mission) => mission.id === missionId) && (
              <option value={missionId}>
                {current.data?.name ?? missionId}
              </option>
            )}
          {missions.map((mission) => (
            <option key={mission.id} value={mission.id}>
              {mission.name}
            </option>
          ))}
        </select>
      </label>
      {page.isError && (
        <p role="status">
          Mission list unavailable. The selected mission and retained drafts
          stay in place.
        </p>
      )}
      {(offset > 0 || missions.length === 50) && (
        <div className="flex gap-2">
          <button
            className="ws-button"
            disabled={offset === 0 || page.isFetching}
            onClick={() => setOffset((n) => Math.max(0, n - 50))}
          >
            Previous missions
          </button>
          <button
            className="ws-button"
            disabled={missions.length < 50 || page.isFetching}
            onClick={() => setOffset((n) => n + 50)}
          >
            More missions
          </button>
        </div>
      )}
    </div>
  );
}
