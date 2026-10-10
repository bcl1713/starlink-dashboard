import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { planningApi } from '../../services/planning';
import type {
  PlanningDraft,
  PlanningView,
  SaveDraft,
  GenerateProposal,
  ApplyProposal,
  SaveReviewed,
} from '../../types/planning';

export function usePlanning(missionId: string, enabled = true) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['planning', missionId],
    queryFn: () => planningApi.read(missionId),
    enabled: enabled && !!missionId,
    retry: false,
  });
  const receive = (view: PlanningView) => {
    client.setQueryData(['planning', missionId], view);
    client.invalidateQueries({ queryKey: ['missions'] });
  };
  const previewRoute = useMutation({
    mutationFn: ({
      legId,
      file,
      expectedRevision,
    }: {
      legId: string;
      file: File;
      expectedRevision: number;
    }) => planningApi.previewRoute(missionId, legId, file, expectedRevision),
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
      planningApi.acceptRoute(missionId, legId, {
        expected_revision: expectedRevision,
        preview_id: previewId,
        discrepancy_acknowledgments: acknowledgments,
      }),
    onSuccess: receive,
  });
  const saveDraft = useMutation({
    mutationFn: ({
      legId,
      draft,
      expectedRevision,
      arSectionStatus,
    }: {
      legId: string;
      draft: PlanningDraft;
      expectedRevision: number;
      arSectionStatus?: SaveDraft['ar_section_status'];
    }) =>
      planningApi.saveDraft(missionId, legId, {
        expected_revision: expectedRevision,
        draft,
        ar_section_status: arSectionStatus,
      }),
    onSuccess: receive,
  });
  const generateProposal = useMutation({
    mutationFn: ({
      legId,
      request,
    }: {
      legId: string;
      request: GenerateProposal;
    }) => planningApi.generateProposal(missionId, legId, request),
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
    }) => planningApi.applyProposal(missionId, legId, request),
    onSuccess: receive,
  });
  const saveReviewed = useMutation({
    mutationFn: ({
      legId,
      request,
    }: {
      legId: string;
      request: SaveReviewed;
    }) => planningApi.saveReviewed(missionId, legId, request),
    onSuccess: receive,
  });
  return {
    ...query,
    previewRoute,
    acceptRoute,
    saveDraft,
    generateProposal,
    applyProposal,
    saveReviewed,
  };
}
