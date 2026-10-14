import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { planningApi } from '../../services/planning';
import { currentLeg } from '../../services/planning-mutations';
import { usePlanningMissionController } from '../usePlanningMissionController';
import type {
  PlanningDraft,
  PlanningView,
  SaveDraft,
  GenerateProposal,
  ApplyProposal,
  SaveReviewed,
  ApplyRevision,
} from '../../types/planning';

export function usePlanning(missionId: string, enabled = true) {
  const client = useQueryClient();
  const controller = usePlanningMissionController(missionId);
  const query = useQuery({
    queryKey: ['planning', missionId],
    queryFn: async () => {
      const received = await planningApi.read(missionId);
      const saved = controller.currentView();
      return saved && saved.revision > received.revision ? saved : received;
    },
    enabled: enabled && !!missionId,
    retry: false,
  });
  const receive = (view: PlanningView) => {
    if (view.revision >= (controller.currentView()?.revision ?? 0))
      client.setQueryData(['planning', missionId], view);
    client.invalidateQueries({ queryKey: ['missions'] });
  };
  const previewRoute = useMutation({
    mutationFn: ({
      legId,
      file,
    }: {
      legId: string;
      file: File;
      expectedRevision: number;
    }) =>
      controller.enqueueMutation(
        (current) =>
          planningApi.previewRoute(missionId, legId, file, current.revision),
        () => null
      ),
  });
  const acceptRoute = useMutation({
    mutationFn: ({
      legId,
      previewId,
      expectedRevision,
      acknowledgments,
    }: {
      legId: string;
      previewId: string;
      expectedRevision: number;
      acknowledgments: string[];
    }) =>
      controller.enqueueMutation(
        () =>
          planningApi.acceptRoute(missionId, legId, {
            expected_revision: expectedRevision,
            preview_id: previewId,
            discrepancy_acknowledgments: acknowledgments,
          }),
        (result) => result
      ),
    onSuccess: receive,
  });
  const saveDraft = useMutation({
    mutationFn: ({
      legId,
      draft,
      inputIdentity,
      expectedRevision,
      arSectionStatus,
    }: {
      legId: string;
      draft: PlanningDraft;
      expectedRevision: number;
      arSectionStatus?: SaveDraft['ar_section_status'];
      inputIdentity?: string;
    }) =>
      controller.enqueueMutation(
        (current) => {
          if (!inputIdentity && current.revision !== expectedRevision)
            throw Object.assign(new Error('Planning state changed'), {
              response: { status: 409 },
            });
          currentLeg(current, legId, inputIdentity);
          return planningApi.saveDraft(missionId, legId, {
            expected_revision: current.revision,
            draft,
            ar_section_status: arSectionStatus,
          });
        },
        (result) => result
      ),
    onSuccess: receive,
  });
  const generateProposal = useMutation({
    mutationFn: ({
      legId,
      request,
    }: {
      legId: string;
      request: GenerateProposal;
    }) =>
      controller.enqueueMutation(
        (current) => {
          currentLeg(current, legId, request.input_identity);
          return planningApi.generateProposal(missionId, legId, {
            ...request,
            expected_revision: current.revision,
          });
        },
        () => null
      ),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ['planning', missionId] }),
  });
  const applyProposal = useMutation({
    mutationFn: ({
      legId,
      request,
    }: {
      legId: string;
      request: ApplyProposal;
    }) =>
      controller.enqueueMutation(
        (current) => {
          currentLeg(current, legId, request.input_identity);
          return planningApi.applyProposal(missionId, legId, {
            ...request,
            expected_revision: current.revision,
          });
        },
        (result) => result
      ),
    onSuccess: receive,
  });
  const saveReviewed = useMutation({
    mutationFn: ({
      legId,
      request,
    }: {
      legId: string;
      request: SaveReviewed;
    }) =>
      controller.enqueueMutation(
        (current) => {
          currentLeg(current, legId, request.input_identity);
          return planningApi.saveReviewed(missionId, legId, {
            ...request,
            expected_revision: current.revision,
          });
        },
        (result) => result
      ),
    onSuccess: receive,
  });
  const previewRevision = useMutation({
    mutationFn: ({ file }: { file: File; expectedRevision: number }) =>
      controller.enqueueMutation(
        (current) =>
          planningApi.previewRevision(missionId, file, current.revision),
        () => null
      ),
  });
  const applyRevision = useMutation({
    mutationFn: (request: ApplyRevision) =>
      controller.enqueueMutation(
        () => planningApi.applyRevision(missionId, request),
        (result) => result
      ),
    onSuccess: receive,
  });
  return {
    controller,
    previewRevision,
    applyRevision,
    ...query,
    previewRoute,
    acceptRoute,
    saveDraft,
    generateProposal,
    applyProposal,
    saveReviewed,
  };
}
