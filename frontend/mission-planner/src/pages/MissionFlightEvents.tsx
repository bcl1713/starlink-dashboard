import { UtcDateTime } from '@/components/operator/UtcDateTime';
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { telemetryArchivesApi } from '@/services/telemetry-archives';

const labels: Record<string, string> = {
  off_blocks: 'Off blocks',
  takeoff: 'Takeoff',
  landed: 'Landed',
  on_blocks: 'Parked',
  stop_classified: 'Stop classification',
};

export function MissionFlightEvents({
  missionId,
  legs,
}: {
  missionId: string;
  legs: { id: string; name: string }[];
}) {
  const [selectedLeg, setSelectedLeg] = useState('');
  const leg = selectedLeg || legs[0]?.id || '';
  const [kind, setKind] = useState('off_blocks');
  const [target, setTarget] = useState('');
  const [time, setTime] = useState('');
  const [reason, setReason] = useState('');
  const [jobId, setJobId] = useState('');
  const health = useQuery({
    queryKey: ['flight-recording-health'],
    queryFn: telemetryArchivesApi.health,
    retry: false,
    refetchInterval: 5000,
  });
  const view = useQuery({
    queryKey: ['flight-events', missionId, leg],
    queryFn: () => telemetryArchivesApi.events(missionId, leg),
    enabled: !!leg,
    retry: false,
    refetchInterval: 10000,
  });
  const save = useMutation({
    mutationFn: async () => {
      const event = view.data?.events.find(
        (event) => event.event_id === target
      );
      if (kind === 'destination_complete' || kind === 'intermediate') {
        if (!event || event.kind !== 'on_blocks')
          throw new Error('Select a parking event');
        return telemetryArchivesApi.classify(
          missionId,
          leg,
          event,
          kind,
          reason
        );
      }
      const occurredAt = new Date(`${time}:00Z`).toISOString();
      return event
        ? telemetryArchivesApi.correct(
            missionId,
            leg,
            event,
            occurredAt,
            reason
          )
        : telemetryArchivesApi.create(missionId, leg, {
            kind,
            occurred_at: occurredAt,
            reason,
          });
    },
    onSuccess: () => {
      setReason('');
      void view.refetch();
    },
  });
  const prepare = useMutation({
    mutationFn: () => telemetryArchivesApi.prepare(missionId, true),
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useQuery({
    queryKey: ['telemetry-preparation', missionId, jobId],
    queryFn: () => telemetryArchivesApi.preparation(missionId, jobId),
    enabled: !!jobId,
    refetchInterval: (query) =>
      ['queued', 'preparing'].includes(query.state.data?.state || '')
        ? 1000
        : false,
  });
  if (!legs.length) return null;
  return (
    <section
      aria-label="Flight recording"
      className="my-6 space-y-3 rounded border p-4"
    >
      <h2 className="text-lg font-semibold">Flight recording</h2>
      <label>
        Leg{' '}
        <select
          aria-label="Recording leg"
          value={leg}
          onChange={(event) => {
            setSelectedLeg(event.target.value);
            setTarget('');
            save.reset();
          }}
        >
          {legs.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {health.data?.mode === 'simulation' ? (
        <p role="status">
          Live recording paused in simulation. Displaying retained live history.
        </p>
      ) : health.data && health.data.state !== 'ready' ? (
        <div role="status">
          {!health.data.detection_available && (
            <p>
              Automatic landing detection unavailable. Movement requires
              operator reconciliation.
            </p>
          )}
          {!health.data.recording_available && (
            <p>Telemetry recording unavailable. Live history may have gaps.</p>
          )}
          <p>{health.data.message}</p>
          {health.data.retry_in_seconds != null && (
            <p>
              Automatic retry in {Math.ceil(health.data.retry_in_seconds)}{' '}
              seconds.
            </p>
          )}
        </div>
      ) : health.isError ? (
        <p role="status">
          Recording readiness unavailable. Refresh to check detection and
          capture status.
        </p>
      ) : null}
      {view.isError ? (
        <p role="status">
          Flight history unavailable. Review recording status and retry;
          preserve existing archive files.
        </p>
      ) : (
        view.data && (
          <>
            <p>
              {view.data.status.movement_uncertain
                ? 'Movement uncertain — operator confirmation may be needed.'
                : `Movement: ${view.data.status.movement_state.replaceAll('_', ' ')}`}
            </p>
            <p>
              Recording:{' '}
              {view.data.status.capture_state?.replaceAll('_', ' ') ||
                'Awaiting departure'}
            </p>
            {view.data.capture.start && (
              <p>
                Capture starts {view.data.capture.start}
                {view.data.capture.end
                  ? `; ends ${view.data.capture.end}`
                  : '; end pending'}{' '}
                (UTC)
              </p>
            )}
            {!!view.data.capture.gaps?.length && (
              <p role="status">
                Recorded gaps: {view.data.capture.gaps.length}. Missing history
                may be unrecoverable; corrections create a new archive revision.
              </p>
            )}
            <ol>
              {view.data.events.map((event) => (
                <li key={event.event_id}>
                  {event.kind === 'landed' && event.source === 'inferred'
                    ? 'Estimated landing'
                    : labels[event.kind] || event.kind}
                  : {event.occurred_at} ({event.source})
                  {event.source === 'inferred' && event.detected_at && (
                    <>; confirmed {event.detected_at}</>
                  )}
                </li>
              ))}
            </ol>
            <details>
              <summary>Confirm or correct flight events</summary>
              <p>
                Parking is the first confirmed destination stop, including DV
                offload. Later repositioning does not extend recording. All
                entered times are UTC.
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  save.mutate();
                }}
                className="space-y-2"
              >
                <label>
                  Action{' '}
                  <select
                    value={kind}
                    onChange={(event) => {
                      setKind(event.target.value);
                      setTarget('');
                    }}
                  >
                    {Object.entries(labels)
                      .filter(([key]) => key !== 'stop_classified')
                      .map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    <option value="destination_complete">
                      Confirm destination parking
                    </option>
                    <option value="intermediate">Mark intermediate stop</option>
                  </select>
                </label>
                <label>
                  Event{' '}
                  <select
                    aria-label="Event to correct"
                    value={target}
                    onChange={(event) => setTarget(event.target.value)}
                  >
                    <option value="">Record a missing event</option>
                    {view.data.events
                      .filter(
                        (event) =>
                          event.kind ===
                          (['destination_complete', 'intermediate'].includes(
                            kind
                          )
                            ? 'on_blocks'
                            : kind)
                      )
                      .map((event) => (
                        <option key={event.event_id} value={event.event_id}>
                          {labels[event.kind]} — {event.occurred_at}
                        </option>
                      ))}
                  </select>
                </label>
                {!['destination_complete', 'intermediate'].includes(kind) && (
                  <UtcDateTime
                    label="Observed time"
                    required
                    value={time ? `${time}:00Z` : null}
                    onChange={(value) => setTime(value?.slice(0, 16) ?? '')}
                  />
                )}
                <label>
                  Reason{' '}
                  <input
                    aria-label="Reason"
                    required
                    maxLength={1000}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </label>
                <button type="submit" disabled={save.isPending}>
                  Record event
                </button>
                {save.isError && (
                  <p role="alert">
                    Could not save. Check event order, select the correct event,
                    and refresh before retrying.
                  </p>
                )}
                {save.isSuccess && <p role="status">Event recorded.</p>}
              </form>
            </details>
          </>
        )
      )}
      <div className="space-x-3">
        <button disabled={prepare.isPending} onClick={() => prepare.mutate()}>
          Prepare telemetry download
        </button>
      </div>
      {prepare.isError && (
        <p role="alert">Could not prepare telemetry. Please try again.</p>
      )}
      {job.data && (
        <p role="status">
          Telemetry package: {job.data.state}
          {job.data.warning_code === 'partial_telemetry' ? ' — partial' : ''}
        </p>
      )}
      {job.data?.state === 'ready' && job.data.download_url && (
        <a href={job.data.download_url} download>
          Download mission telemetry
        </a>
      )}
    </section>
  );
}
