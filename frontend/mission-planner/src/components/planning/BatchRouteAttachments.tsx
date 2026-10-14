import { useEffect, useRef, useState } from 'react';
import type { BatchRoutePreview, PlanningView } from '../../types/planning';
import { usePlanningMissionController } from '../../hooks/usePlanningMissionController';
import { planningApi, planningErrorMessage } from '../../services/planning';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

const suggested = (preview: BatchRoutePreview | null) =>
  Object.fromEntries(
    (preview?.attachments ?? []).map((item) => [
      item.attachment_id,
      item.suggested_leg_id ?? '',
    ])
  );
export function BatchRouteAttachments({
  view,
  onAccepted,
  initialFiles = [],
  initialPreview = null,
}: {
  view: PlanningView;
  onAccepted: (view: PlanningView) => void;
  initialFiles?: File[];
  initialPreview?: BatchRoutePreview | null;
}) {
  const missionId = view.mission.id;
  const controller = usePlanningMissionController(missionId);
  const [files, setFiles] = useState(initialFiles);
  const [preview, setPreview] = useState(initialPreview);
  const [assignments, setAssignments] = useState(suggested(initialPreview));
  const [acknowledgments, setAcknowledgments] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const legs = view.expected_legs.filter((card) => !card.leg.retired);
  const chosen = (preview?.attachments ?? []).filter(
    (item) => assignments[item.attachment_id] && !item.errors.length
  );
  const duplicate =
    new Set(chosen.map((item) => assignments[item.attachment_id])).size !==
    chosen.length;
  const candidate = (id: string, leg: string) =>
    preview?.attachments
      .find((item) => item.attachment_id === id)
      ?.candidates.find((item) => item.leg_id === leg);
  const key = (id: string, leg: string, code: string) => `${id}:${leg}:${code}`;
  const missing = chosen.some((item) =>
    candidate(
      item.attachment_id,
      assignments[item.attachment_id]
    )?.discrepancy_errors.some(
      (issue) =>
        !acknowledgments.includes(
          key(item.attachment_id, assignments[item.attachment_id], issue.code)
        )
    )
  );
  const stage = async () => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      if (preview?.attachments.some((item) => !item.errors.length))
        await planningApi.discardRoutes(missionId, preview.preview_id);
      setPreview(null);
      const result = await controller.enqueueMutation(
        (current) =>
          planningApi.previewRoutes(missionId, files, current.revision),
        () => null
      );
      if (!alive.current) {
        if (result.attachments.some((item) => !item.errors.length))
          await planningApi.discardRoutes(missionId, result.preview_id);
        return;
      }
      setPreview(result);
      setAssignments(suggested(result));
      setAcknowledgments([]);
    } catch (failure) {
      if (alive.current) setError(planningErrorMessage(failure));
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const discard = async () => {
    if (!preview) return;
    setBusy(true);
    setError('');
    try {
      if (preview.attachments.some((item) => !item.errors.length))
        await planningApi.discardRoutes(missionId, preview.preview_id);
      setPreview(null);
      setMessage('Staged attachments discarded.');
    } catch (failure) {
      setError(planningErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const accept = async () => {
    if (!preview || !chosen.length || duplicate || missing) return;
    setBusy(true);
    setError('');
    try {
      const result = await controller.enqueueMutation(
        () =>
          planningApi.acceptRoutes(missionId, {
            preview_id: preview.preview_id,
            expected_revision: preview.expected_revision,
            assignments: chosen.map((item) => ({
              attachment_id: item.attachment_id,
              leg_id: assignments[item.attachment_id],
              discrepancy_acknowledgments: (
                candidate(item.attachment_id, assignments[item.attachment_id])
                  ?.discrepancy_errors ?? []
              ).map((issue) => issue.code),
            })),
          }),
        (result) => result
      );
      if (alive.current) {
        setPreview(null);
        setMessage('Routes attached. Review AR windows and plans next.');
        onAccepted(result);
      }
    } catch (failure) {
      if (alive.current) setError(planningErrorMessage(failure));
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  return (
    <fieldset
      disabled={busy}
      aria-label="Batch route attachments"
      className="min-w-0 space-y-3 rounded border p-4"
    >
      <legend className="font-semibold">Route attachments</legend>
      <p>
        Attach KMLs together before reviewing route-dependent AR windows.
        Suggestions use airports and UTC timing. Confirm each assignment;
        filenames do not select a leg.
      </p>
      <label>
        Route KMLs
        <Input
          aria-label="Route KMLs"
          type="file"
          accept=".kml"
          multiple
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />
      </label>
      <p className="text-sm">Up to 16 KMLs, 10 MiB each, 40 MiB total.</p>
      <Button onClick={stage} disabled={busy || !files.length}>
        Preview route attachments
      </Button>
      {busy && <p role="status">Processing route attachments…</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {preview?.attachments.map((item) => {
        const selected = assignments[item.attachment_id] ?? '';
        const match = candidate(item.attachment_id, selected);
        const card = legs.find((card) => card.leg.id === selected);
        return (
          <section
            key={item.attachment_id}
            className="space-y-2 rounded border p-3"
          >
            <h3 className="break-words font-semibold">{item.filename}</h3>
            {item.source_departure_time && (
              <p className="break-words">
                Source {item.departure_airport} → {item.arrival_airport} ·
                Source UTC {item.source_departure_time} →{' '}
                {item.source_arrival_time}
              </p>
            )}
            {card && (
              <p className="break-words">
                Expected UTC {card.leg.departure_time} → {card.leg.arrival_time}
              </p>
            )}
            {item.errors.map((issue) => (
              <p key={issue.code} role="alert">
                {issue.message}
              </p>
            ))}
            {!item.suggested_leg_id && !item.errors.length && (
              <p>
                Assignment required: source evidence is ambiguous or unmatched.
              </p>
            )}
            <label>
              Assign {item.filename}
              <select
                aria-label={`Assign ${item.filename}`}
                className="block min-h-11 w-full rounded border bg-background p-2"
                value={selected}
                disabled={!!item.errors.length}
                onChange={(event) =>
                  setAssignments({
                    ...assignments,
                    [item.attachment_id]: event.target.value,
                  })
                }
              >
                <option value="">Skip attachment</option>
                {legs.map((card) => (
                  <option key={card.leg.id} value={card.leg.id}>
                    Leg {card.leg.ordinal}: {card.leg.departure_airport} →{' '}
                    {card.leg.arrival_airport}
                  </option>
                ))}
              </select>
            </label>
            {match && (
              <p>
                {match.reasons
                  .map((reason) =>
                    reason === 'airports_match'
                      ? 'Airports match'
                      : 'UTC window matches'
                  )
                  .join(' · ') || 'No matching airport or UTC evidence'}
              </p>
            )}
            {card?.leg.route && (
              <p>
                Replacing Leg {card.leg.ordinal} route. Prior source history,
                corrections and installed plan are retained for review.
              </p>
            )}
            {match?.discrepancy_errors.map((issue) => (
              <label
                key={issue.code}
                className="flex min-h-11 items-center gap-2"
              >
                <input
                  type="checkbox"
                  aria-label={`Acknowledge ${item.filename}: ${issue.message}`}
                  checked={acknowledgments.includes(
                    key(item.attachment_id, selected, issue.code)
                  )}
                  onChange={(event) =>
                    setAcknowledgments((current) =>
                      event.target.checked
                        ? [
                            ...current,
                            key(item.attachment_id, selected, issue.code),
                          ]
                        : current.filter(
                            (value) =>
                              value !==
                              key(item.attachment_id, selected, issue.code)
                          )
                    )
                  }
                />
                {issue.message}
              </label>
            ))}
          </section>
        );
      })}
      {duplicate && (
        <p role="alert">Choose one attachment per leg before accepting.</p>
      )}
      {preview && (
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={accept}
            disabled={busy || !chosen.length || duplicate || missing}
          >
            Accept route bindings
          </Button>
          <Button variant="outline" onClick={discard}>
            Discard staged attachments
          </Button>
        </div>
      )}
    </fieldset>
  );
}
