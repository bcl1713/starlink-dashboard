import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { usePlanning } from '../../hooks/api/usePlanning';
import {
  planningApi,
  planningErrorMessage,
  planningDisplayCount,
} from '../../services/planning';
import { routesApi } from '../../services/routes';
import type {
  ExpectedLegCard,
  PlanningDraft,
  PlanningView,
  RouteBindingPreview,
} from '../../types/planning';
import { ARReview } from './ARReview';
import { PermittedSatellites } from './PermittedSatellites';
import { PlanningXDraft } from './PlanningXDraft';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { KaOutageConfig } from '../satellites/KaOutageConfig';
import { KuOutageConfig } from '../satellites/KuOutageConfig';
import { ManualAARTrackEditor } from '../aar/ManualAARTrackEditor';

export function PlanningLegReview({
  missionId,
  legId,
}: {
  missionId: string;
  legId: string;
}) {
  const planning = usePlanning(missionId);
  const card = planning.data?.expected_legs.find(
    (card) => !card.leg.retired && card.leg.id === legId
  );
  if (!planning.data)
    return (
      <div className="app-page">
        {planning.isLoading ? (
          'Loading planning draft…'
        ) : (
          <p role="alert">{planningErrorMessage(planning.error)}</p>
        )}
      </div>
    );
  if (!card)
    return (
      <div className="app-page">
        <p role="alert">
          Expected leg not found. Return to the mission and select a current
          leg.
        </p>
      </div>
    );
  return (
    <ReviewEditor
      key={legId}
      card={card}
      view={planning.data}
      planning={planning}
    />
  );
}
function ReviewEditor({
  card,
  view,
  planning,
}: {
  card: ExpectedLegCard;
  view: PlanningView;
  planning: ReturnType<typeof usePlanning>;
}) {
  const navigate = useNavigate();
  const leg = card.leg;
  const [draft, setDraft] = useState<PlanningDraft>(() => ({
    ...leg.draft,
    ar_corrections: leg.draft?.ar_corrections?.length
      ? leg.draft.ar_corrections
      : (leg.ar_rows ?? []),
  }));
  const [section, setSection] = useState(leg.ar_section_status ?? 'empty');
  const [expectedRevision, setExpectedRevision] = useState(view.revision);
  const [dirty, setDirty] = useState(false);
  const [tab, setTab] = useState('ar');
  const [file, setFile] = useState<File | null>(null);
  const [routePreview, setRoutePreview] = useState<RouteBindingPreview | null>(
    null
  );
  const [acknowledgments, setAcknowledgments] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const arTab = useRef<HTMLButtonElement>(null);
  const options = useQuery({
    queryKey: ['planning-satellite-options'],
    queryFn: planningApi.satelliteOptions,
    retry: false,
  });
  const coordinates = useQuery({
    queryKey: ['planning-route-detail', leg.route?.route_id],
    queryFn: () => routesApi.get(leg.route!.route_id),
    enabled: !!leg.route,
  });
  const change = (updates: Partial<PlanningDraft>) => {
    setDraft((current) => ({ ...current, ...updates }));
    setDirty(true);
    setMessage('');
  };
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty]);
  const returnToMission = () => {
    if (
      !dirty ||
      window.confirm(
        'You have unsaved changes. Are you sure you want to leave?'
      )
    )
      navigate(`/missions/${view.mission.id}`);
  };
  const preview = async () => {
    if (!file) return;
    setError('');
    setMessage('');
    try {
      const staged = await planning.previewRoute.mutateAsync({
        legId: leg.id,
        file,
        expectedRevision,
      });
      setRoutePreview(staged);
      setAcknowledgments([]);
    } catch (e) {
      setError(planningErrorMessage(e));
    }
  };
  const accept = async () => {
    if (!routePreview) return;
    setError('');
    try {
      const accepted = await planning.acceptRoute.mutateAsync({
        legId: leg.id,
        previewId: routePreview.preview_id,
        expectedRevision: routePreview.expected_revision,
        acknowledgments,
      });
      const current = accepted.expected_legs.find(
        (card) => card.leg.id === leg.id
      )!.leg;
      if (!dirty)
        setDraft({
          ...current.draft,
          ar_corrections: current.draft?.ar_corrections?.length
            ? current.draft.ar_corrections
            : (current.ar_rows ?? []),
        });
      setExpectedRevision(accepted.revision);
      setTab('ar');
      setMessage('Route accepted. Review AR windows first.');
      setTimeout(() => arTab.current?.focus(), 0);
    } catch (e) {
      setError(planningErrorMessage(e));
    }
  };
  const save = async () => {
    setError('');
    setMessage('');
    try {
      const saved = await planning.saveDraft.mutateAsync({
        legId: leg.id,
        draft,
        expectedRevision,
        arSectionStatus: section,
      });
      const current = saved.expected_legs.find(
        (card) => card.leg.id === leg.id
      )!.leg;
      setDraft(current.draft ?? {});
      setSection(current.ar_section_status ?? 'empty');
      setExpectedRevision(saved.revision);
      setDirty(false);
      setMessage('Draft saved.');
    } catch (e) {
      setError(planningErrorMessage(e));
    }
  };
  const pending =
    planning.previewRoute.isPending ||
    planning.acceptRoute.isPending ||
    planning.saveDraft.isPending;
  return (
    <fieldset
      className="app-page min-w-0 space-y-6"
      disabled={planning.saveDraft.isPending || planning.acceptRoute.isPending}
      aria-label="Leg planning draft"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">
            Leg {leg.ordinal} of {planningDisplayCount(view)} ·{' '}
            {leg.departure_airport} → {leg.arrival_airport}
          </h1>
          <p className="break-words text-sm">
            UTC {leg.departure_time} → {leg.arrival_time}
          </p>
        </div>
        <Button variant="outline" onClick={returnToMission}>
          Return to mission
        </Button>
      </div>
      <section
        aria-label="Selected-leg KML upload"
        className="min-w-0 space-y-3 rounded-xl border p-4"
      >
        <h2 className="font-semibold">
          {leg.route ? 'Replace selected-leg KML' : 'Upload selected-leg KML'}
        </h2>
        {leg.route && (
          <p className="break-words text-sm">
            Accepted route: {leg.route.filename}
          </p>
        )}
        <label>
          KML for leg {leg.ordinal}
          <Input
            aria-label={`KML for leg ${leg.ordinal}`}
            type="file"
            accept=".kml,application/vnd.google-earth.kml+xml"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setRoutePreview(null);
              setAcknowledgments([]);
            }}
          />
        </label>
        <Button onClick={preview} disabled={!file || pending}>
          Preview selected-leg KML
        </Button>
        {routePreview && (
          <div className="space-y-3">
            <p className="break-words">
              Preview for leg {leg.ordinal}: {routePreview.binding.filename}
            </p>
            {routePreview.discrepancy_errors?.map((issue, index) => (
              <div key={index}>
                <p role="alert" className="text-destructive">
                  {issue.message}
                </p>
                <label className="flex min-h-11 items-center gap-2">
                  <input
                    type="checkbox"
                    aria-label={`Acknowledge: ${issue.message}`}
                    checked={acknowledgments.includes(issue.code)}
                    onChange={(e) =>
                      setAcknowledgments(
                        e.target.checked
                          ? [...acknowledgments, issue.code]
                          : acknowledgments.filter(
                              (code) => code !== issue.code
                            )
                      )
                    }
                  />
                  I acknowledge this route discrepancy
                </label>
              </div>
            ))}
            <Button
              onClick={accept}
              className="h-auto min-h-11 max-w-full whitespace-normal"
              disabled={
                pending ||
                !!routePreview.discrepancy_errors?.some(
                  (issue) => !acknowledgments.includes(issue.code)
                )
              }
            >
              Accept route and review AR windows
            </Button>
          </div>
        )}
      </section>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {view.revision !== expectedRevision && (
        <p role="alert">
          This mission has a newer revision. Save will check your original
          revision; reload to reconcile other changes.
        </p>
      )}
      {options.data ? (
        <PermittedSatellites
          options={options.data}
          value={draft}
          onChange={change}
        />
      ) : (
        <p role="alert">
          {options.error
            ? 'Unable to load configured satellites. Retry by reloading; draft edits remain available.'
            : 'Loading configured satellites…'}
        </p>
      )}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="max-w-full justify-start overflow-x-auto">
          <TabsTrigger ref={arTab} value="ar">
            AR windows
          </TabsTrigger>
          <TabsTrigger value="x">X-band plan</TabsTrigger>
          <TabsTrigger value="ka">Ka outages</TabsTrigger>
          <TabsTrigger value="ku">Ku outages</TabsTrigger>
          <TabsTrigger value="manual">Manual AR Tracks</TabsTrigger>
        </TabsList>
        <TabsContent value="ar">
          <ARReview
            leg={leg}
            rows={draft.ar_corrections ?? []}
            onChange={(rows) =>
              change({ ar_corrections: rows, no_ars_confirmed: false })
            }
            sectionStatus={section}
            onSectionStatusChange={(value) => {
              setSection(value);
              change({ no_ars_confirmed: false });
            }}
            noARsConfirmed={draft.no_ars_confirmed ?? false}
            onNoARsConfirmedChange={(value) =>
              change({ no_ars_confirmed: value })
            }
            candidates={routePreview?.matched_ar_candidates}
            coordinates={(coordinates.data?.points ?? []).map((point) => [
              point.latitude,
              point.longitude,
            ])}
            routePoints={coordinates.data?.points ?? []}
          />
          {coordinates.error && (
            <p role="alert">
              Route geometry could not be loaded. Reload before confirming map
              spans.
            </p>
          )}
        </TabsContent>
        <TabsContent value="x">
          <PlanningXDraft
            leg={leg}
            draft={draft}
            onChange={change}
            options={options.data ?? { satellites: [] }}
          />
        </TabsContent>
        <TabsContent value="ka">
          <KaOutageConfig
            outages={draft.ka_outages ?? []}
            onOutagesChange={(ka_outages) => change({ ka_outages })}
          />
        </TabsContent>
        <TabsContent value="ku">
          <KuOutageConfig
            outages={draft.ku_overrides ?? []}
            onOutagesChange={(ku_overrides) => change({ ku_overrides })}
          />
        </TabsContent>
        <TabsContent value="manual">
          <ManualAARTrackEditor
            tracks={draft.manual_aar_tracks ?? []}
            onSaveTrack={async (track) => {
              change({
                manual_aar_tracks: [
                  ...(draft.manual_aar_tracks ?? []).filter(
                    (existing) => existing.id !== track.id
                  ),
                  track,
                ],
              });
            }}
            onRemoveTrack={(id) =>
              change({
                manual_aar_tracks: draft.manual_aar_tracks?.filter(
                  (track) => track.id !== id
                ),
              })
            }
          />
        </TabsContent>
      </Tabs>
      <p className="text-sm text-muted-foreground">
        Manual draft edits are available. Automatic optimization and saving
        reviewed plans are not yet available.
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" onClick={returnToMission}>
          Cancel
        </Button>
        <Button onClick={save} disabled={pending}>
          {planning.saveDraft.isPending ? 'Saving…' : 'Save draft'}
        </Button>
        <Button disabled>Save reviewed plan</Button>
      </div>
    </fieldset>
  );
}
