import { useEffect, useRef, useState } from 'react';
import type { usePlanning } from './api/usePlanning';
import { planningApi, planningErrorMessage } from '../services/planning';
import { planningSourceReady } from '../services/planning-prerequisites';
import type {
  ExpectedLegCard,
  PlanningView,
  PlanningDraft,
  PlanningEvaluation,
  PlanningProposal,
  PlanningManifest,
  PlanningSatelliteOptions,
  RouteBindingPreview,
} from '../types/planning';

/** Owns captured CAS and local edits across the complete managed leg workflow. */
export function usePlanningLegWorkflow({
  card,
  view,
  planning,
  satelliteOptions,
  navigate,
  onAcceptedRoute,
}: {
  card: ExpectedLegCard;
  view: PlanningView;
  planning: ReturnType<typeof usePlanning>;
  satelliteOptions?: PlanningSatelliteOptions;
  navigate: (path: string) => void;
  onAcceptedRoute: () => void;
}) {
  const leg = card.leg;
  const controller = planning.controller;
  const editEpoch = useRef(0);
  const autosavedEpoch = useRef(0);
  const [draft, setDraft] = useState<PlanningDraft>(() => ({
    ...leg.draft,
    ar_corrections: leg.draft?.ar_corrections?.length
      ? leg.draft.ar_corrections
      : (leg.ar_rows ?? []),
  }));
  const [section, setSection] = useState(leg.ar_section_status ?? 'empty');
  const [expectedRevision, setExpectedRevision] = useState(view.revision);
  const [dirty, setDirty] = useState(false);
  const [sequencePending, setSequencePending] = useState(false);
  const [inputIdentity, setInputIdentity] = useState(card.input_identity);
  const [proposal, setProposal] = useState<PlanningProposal | null>(null);
  const [resumeView, setResumeView] = useState({ view });
  const currentInputs = useRef({ dirty, expectedRevision, inputIdentity });
  currentInputs.current = { dirty, expectedRevision, inputIdentity };
  useEffect(() => {
    const manifest = resumeView.view.mission.metadata?.itinerary_planning as
      | PlanningManifest
      | undefined;
    const reference = manifest?.proposal_refs
      ?.filter((item) => item.leg_id === leg.id)
      .at(-1);
    if (!reference) return;
    let current = true;
    planningApi
      .readProposal(resumeView.view.mission.id, leg.id, reference.id)
      .then((saved) => {
        if (!current) return;
        const inputs = currentInputs.current;
        const stale =
          inputs.dirty ||
          saved.state === 'stale' ||
          (saved.applied_input_identity ?? saved.input_identity) !==
            inputs.inputIdentity;
        setProposal(stale ? { ...saved, state: 'stale' } : saved);
      })
      .catch((failure) => {
        if (current) setError(planningErrorMessage(failure));
      });
    return () => {
      current = false;
    };
  }, [resumeView, leg.id]);
  const [evaluation, setEvaluation] = useState<PlanningEvaluation | null>(null);
  const [previewError, setPreviewError] = useState('');
  const [planConfirmed, setPlanConfirmed] = useState(false);
  const [gapAcknowledged, setGapAcknowledged] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [routePreview, setRoutePreview] = useState<RouteBindingPreview | null>(
    null
  );
  const [acknowledgments, setAcknowledgments] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const change = (updates: Partial<PlanningDraft>) => {
    controller.cancelPreview(leg.id);
    editEpoch.current++;
    setDraft((current) => ({ ...current, ...updates }));
    setDirty(true);
    setEvaluation(null);
    setPlanConfirmed(false);
    setGapAcknowledged(false);
    setProposal((current) => (current ? { ...current, state: 'stale' } : null));
    setMessage('');
  };
  useEffect(() => {
    if (!leg.route || !draft.initial_x_satellite_id) return;
    let current = true;
    const token = controller.beginPreview(
      leg.id,
      JSON.stringify({ draft, section })
    );
    const timer = setTimeout(() => {
      planningApi
        .previewDraft(view.mission.id, leg.id, {
          expected_revision:
            controller.currentView()?.revision ?? expectedRevision,
          draft,
          ar_section_status: section,
        })
        .then((result) => {
          if (current && controller.acceptPreview(token, result)) {
            setEvaluation(result);
            setPreviewError('');
          }
        })
        .catch((error) => {
          if (current) {
            setEvaluation(null);
            setPreviewError(planningErrorMessage(error));
          }
        });
    }, 300);
    return () => {
      current = false;
      clearTimeout(timer);
      controller.cancelPreview(leg.id);
    };
  }, [
    controller,
    draft,
    expectedRevision,
    leg.id,
    leg.route,
    section,
    view.mission.id,
  ]);
  const receive = (saved: PlanningView) => {
    const current = saved.expected_legs.find((c) => c.leg.id === leg.id)!;
    setDraft(current.leg.draft ?? {});
    setSection(current.leg.ar_section_status ?? 'empty');
    setExpectedRevision(saved.revision);
    setInputIdentity(current.input_identity);
    setDirty(false);
    setEvaluation(null);
    setPlanConfirmed(false);
    setGapAcknowledged(false);
    return current;
  };
  useEffect(() => {
    if (view.revision < expectedRevision) return;
    const current = view.expected_legs.find((item) => item.leg.id === leg.id);
    if (!current) return;
    if (current.input_identity === inputIdentity) {
      setExpectedRevision(view.revision);
    } else if (!dirty) {
      receive(view);
      setProposal((current) =>
        current ? { ...current, state: 'stale' } : null
      );
    } else {
      setError(
        'Planning inputs changed. Local edits are retained; reload explicitly before saving.'
      );
    }
    // Observe committed views without replacing unsaved work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, leg.id]);
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
    setSequencePending(true);
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
      setInputIdentity(
        accepted.expected_legs.find((c) => c.leg.id === leg.id)!.input_identity
      );
      setRoutePreview(null);
      setEvaluation(null);
      setPlanConfirmed(false);
      setGapAcknowledged(false);
      setProposal(null);
      onAcceptedRoute();
      setMessage('Route accepted. Review AR windows first.');
      if (!leg.route) {
        let ready = accepted;
        if (dirty) {
          const merged = {
            ...current.draft,
            ...draft,
            ar_corrections: draft.ar_corrections?.length
              ? draft.ar_corrections
              : (current.draft?.ar_corrections ?? current.ar_rows ?? []),
          };
          ready = await planning.saveDraft.mutateAsync({
            legId: leg.id,
            draft: merged,
            expectedRevision: accepted.revision,
            arSectionStatus: section,
          });
          receive(ready);
        }
      }
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setSequencePending(false);
    }
  };

  const save = async () => {
    autosavedEpoch.current = editEpoch.current;
    setError('');
    setMessage('');
    try {
      const saved = await planning.saveDraft.mutateAsync({
        legId: leg.id,
        draft,
        expectedRevision,
        inputIdentity,
        arSectionStatus: section,
      });
      receive(saved);
      setMessage('Draft saved.');
      return saved;
    } catch (e) {
      setError(planningErrorMessage(e));
    }
  };
  const optimize = async () => {
    if (!planningSourceReady(leg, draft, section)) return;
    setSequencePending(true);
    setError('');
    const saved = dirty ? await save() : view;
    if (!saved) {
      setSequencePending(false);
      return;
    }
    try {
      const current = saved.expected_legs.find((c) => c.leg.id === leg.id)!;
      const result = await planning.generateProposal.mutateAsync({
        legId: leg.id,
        request: {
          expected_revision: dirty ? saved.revision : expectedRevision,
          input_identity: dirty ? current.input_identity : inputIdentity,
        },
      });
      setProposal(result);
      setMessage(
        'Proposal ready to compare. Apply it explicitly to change your draft.'
      );
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setSequencePending(false);
    }
  };
  const apply = async () => {
    if (!proposal || dirty) return;
    setError('');
    try {
      const saved = await planning.applyProposal.mutateAsync({
        legId: leg.id,
        request: {
          expected_revision: expectedRevision,
          input_identity: inputIdentity,
          proposal_id: proposal.id,
        },
      });
      receive(saved);
      setProposal(null);
      setMessage(
        'Proposal applied to the draft. Review availability before saving.'
      );
    } catch (e) {
      setError(planningErrorMessage(e));
    }
  };
  const reviewed = async (next: boolean) => {
    setError('');
    try {
      const rows = draft.ar_corrections ?? [];
      const saved = await planning.saveReviewed.mutateAsync({
        legId: leg.id,
        request: {
          expected_revision: expectedRevision,
          input_identity: inputIdentity,
          satellite_plan_confirmed: planConfirmed,
          gap_acknowledged: gapAcknowledged,
          no_ars_confirmed: draft.no_ars_confirmed ?? false,
          confirmed_ar_ids: rows
            .filter((r) => r.match_status !== 'excluded')
            .map((r) => r.id),
          excluded_ar_ids: rows
            .filter((r) => r.match_status === 'excluded')
            .map((r) => r.id),
        },
      });
      receive(saved);
      setMessage('Reviewed plan saved as an inactive leg.');
      if (next) {
        const unbound = saved.expected_legs
          .filter((c) => !c.leg.retired && !c.leg.route)
          .sort((a, b) => a.leg.ordinal - b.leg.ordinal)[0];
        navigate(
          unbound
            ? `/missions/${view.mission.id}/legs/${unbound.leg.id}`
            : `/missions/${view.mission.id}`
        );
      }
    } catch (e) {
      setError(planningErrorMessage(e));
    }
  };
  const reload = async () => {
    if (
      dirty &&
      !window.confirm('Discard local edits and reload the current saved draft?')
    )
      return;
    setSequencePending(true);
    setError('');
    setMessage('');
    try {
      const result = await planning.refetch();
      if (result.error) throw result.error;
      if (!result.data) throw new Error('Unable to reload the saved draft');
      receive(result.data);
      setProposal(null);
      setResumeView({ view: result.data });
      setMessage('Saved draft reloaded.');
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setSequencePending(false);
    }
  };
  const readyToGenerate = planningSourceReady(leg, draft, section);
  const invalid =
    !leg.route ||
    !draft.initial_x_satellite_id ||
    !draft.access_confirmation?.confirmed ||
    !draft.permitted_satellite_ids?.length ||
    satelliteOptions?.satellites
      .filter((s) => s.eligible)
      .every((s) => !draft.permitted_satellite_ids?.includes(s.id)) ||
    draft.permitted_satellite_ids?.some(
      (id) =>
        !satelliteOptions?.satellites.some((s) => s.id === id && s.eligible)
    ) ||
    section === 'unrecognized' ||
    !!draft.unresolved_x_transitions?.length ||
    !!draft.unresolved_aar_windows?.length ||
    (draft.ar_corrections ?? []).some(
      (r) =>
        r.match_status !== 'excluded' &&
        (!r.confirmed ||
          r.match_status !== 'matched' ||
          !r.confirmed_units ||
          r.source_altitude == null)
    ) ||
    (!(draft.ar_corrections ?? []).some((r) => r.match_status !== 'excluded') &&
      !draft.no_ars_confirmed);
  const pending =
    sequencePending ||
    planning.previewRoute.isPending ||
    planning.acceptRoute.isPending ||
    planning.saveDraft.isPending ||
    planning.generateProposal.isPending ||
    planning.applyProposal.isPending ||
    planning.saveReviewed.isPending;
  const saveLatest = useRef(save);
  saveLatest.current = save;
  useEffect(() => {
    if (!dirty || pending || autosavedEpoch.current === editEpoch.current)
      return;
    const timer = setTimeout(() => {
      void saveLatest.current();
    }, 500);
    return () => clearTimeout(timer);
  }, [dirty, draft, section, pending]);
  return {
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
    readyToGenerate,
    pending,
  };
}
