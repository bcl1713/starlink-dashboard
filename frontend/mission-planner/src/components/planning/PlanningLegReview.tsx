import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { usePlanning } from '../../hooks/api/usePlanning';
import { usePlanningLegWorkflow } from '../../hooks/usePlanningLegWorkflow';
import {
  planningApi,
  planningErrorMessage,
  planningDisplayCount,
} from '../../services/planning';
import { routesApi } from '../../services/routes';
import type { ExpectedLegCard, PlanningView } from '../../types/planning';
import { ARReview } from './ARReview';
import { PermittedSatellites } from './PermittedSatellites';
import { XBandPlanReview } from './XBandPlanReview';
import { UnresolvedARWindows } from './UnresolvedARWindows';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { KaOutageConfig } from '../satellites/KaOutageConfig';
import { KuOutageConfig } from '../satellites/KuOutageConfig';
import { ManualAARTrackEditor } from '../aar/ManualAARTrackEditor';
import { LegMapVisualization } from '../../pages/LegDetailPage/LegMapVisualization';

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
  const [tab, setTab] = useState('ar');
  const arTab = useRef<HTMLButtonElement>(null);
  const routeInput = useRef<HTMLInputElement>(null);
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
  const {
    draft,
    section,
    setSection,
    expectedRevision,
    dirty,
    proposal,
    evaluation,
    previewError,
    planConfirmed,
    setPlanConfirmed,
    gapAcknowledged,
    setGapAcknowledged,
    file,
    setFile,
    routePreview,
    setRoutePreview,
    acknowledgments,
    setAcknowledgments,
    message,
    error,
    change,
    returnToMission,
    preview,
    accept,
    save,
    optimize,
    apply,
    reviewed,
    reload,
    invalid,
    pending,
  } = usePlanningLegWorkflow({
    card,
    view,
    planning,
    satelliteOptions: options.data,
    navigate,
    onAcceptedRoute: () => {
      setTab('ar');
      setTimeout(() => arTab.current?.focus(), 0);
    },
  });
  return (
    <fieldset
      className="app-page min-w-0 space-y-6"
      disabled={pending}
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
        {leg.route && (
          <Button variant="outline" onClick={() => routeInput.current?.focus()}>
            Update Route
          </Button>
        )}
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
            ref={routeInput}
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
            <Button
              variant="outline"
              onClick={() => {
                setRoutePreview(null);
                setAcknowledgments([]);
                setFile(null);
                if (routeInput.current) routeInput.current.value = '';
              }}
            >
              Cancel route replacement
            </Button>
            {!!routePreview.unresolved_lock_ids?.length && (
              <p role="alert">
                Existing locks need occurrence review:{' '}
                {routePreview.unresolved_lock_ids.join(', ')}
              </p>
            )}
            {!!routePreview.unresolved_ar_ids?.length && (
              <p role="alert">
                Existing AR anchors need review:{' '}
                {routePreview.unresolved_ar_ids.join(', ')}
              </p>
            )}
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
      {previewError && <p role="alert">{previewError}</p>}
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
          <UnresolvedARWindows
            leg={leg}
            draft={draft}
            routePoints={coordinates.data?.points ?? []}
            onChange={change}
          />
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
          <XBandPlanReview
            leg={leg}
            draft={draft}
            onChange={change}
            options={options.data ?? { satellites: [] }}
            routePoints={coordinates.data?.points ?? []}
            evaluation={evaluation}
            proposal={proposal}
            onApply={apply}
            onReoptimize={optimize}
            disabled={pending}
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
      {!!coordinates.data?.points?.length && (
        <LegMapVisualization
          routeCoordinates={coordinates.data.points.map((point) => [
            point.latitude,
            point.longitude,
          ])}
          satelliteConfig={{
            xband_starting_satellite: draft.initial_x_satellite_id ?? undefined,
            xband_transitions: (draft.swaps ?? []).map((swap) => ({
              id: swap.id,
              target_satellite_id: swap.target_satellite_id,
              latitude: swap.anchor.latitude,
              longitude: swap.anchor.longitude,
              anchor: swap.anchor,
            })),
            ka_outages: draft.ka_outages ?? [],
            ku_outages: draft.ku_overrides ?? [],
          }}
          aarConfig={{
            segments: [],
            manualTracks: draft.manual_aar_tracks ?? [],
          }}
          kaTransitions={[]}
          waypointNames={[]}
          availableWaypoints={coordinates.data.waypoints ?? []}
          planningLeg={leg}
          planningDraft={draft}
        />
      )}
      {invalid && (
        <p role="alert">
          Provisional plan: resolve field errors, AR review and current
          satellite access before reviewed save.
        </p>
      )}
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={planConfirmed}
          onChange={(e) => setPlanConfirmed(e.target.checked)}
        />
        I confirm this satellite plan and Starshield enablement
      </label>
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={gapAcknowledged}
          onChange={(e) => setGapAcknowledged(e.target.checked)}
        />
        I acknowledge the X-band outages and backup gaps
      </label>
      {dirty && <p>Save draft before confirming the reviewed plan.</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" onClick={returnToMission}>
          Cancel
        </Button>
        <Button onClick={save} disabled={pending}>
          {planning.saveDraft.isPending ? 'Saving…' : 'Save draft'}
        </Button>
        <Button variant="outline" onClick={reload}>
          Reload saved draft
        </Button>
        <Button
          onClick={() => reviewed(false)}
          disabled={
            pending ||
            dirty ||
            !!invalid ||
            !planConfirmed ||
            !evaluation ||
            !!evaluation.errors?.length ||
            (!!(evaluation.outage_seconds || evaluation.backup_gaps?.length) &&
              !gapAcknowledged)
          }
        >
          Save reviewed plan
        </Button>
        <Button
          className="h-auto min-h-11 whitespace-normal"
          onClick={() => reviewed(true)}
          disabled={
            pending ||
            dirty ||
            !!invalid ||
            !planConfirmed ||
            !evaluation ||
            !!evaluation.errors?.length ||
            (!!(evaluation.outage_seconds || evaluation.backup_gaps?.length) &&
              !gapAcknowledged)
          }
        >
          Save reviewed plan and upload next leg
        </Button>
      </div>
    </fieldset>
  );
}
