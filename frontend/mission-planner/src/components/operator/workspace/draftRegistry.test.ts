// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { callDraft } from '../callDraft';
import { newTransportDraft } from '../transportForms';
import { transportDraftKey } from '@/hooks/api/useOperatorTransportDraft';
import { DraftRegistry } from './draftRegistry';
import { recoverLegacyDrafts } from './legacyRecovery';
import type { DraftTarget } from './types';

const target: DraftTarget = {
  storeId: 'store-a',
  epoch: 'epoch-a',
  sourceMode: 'simulation',
  simulationRunId: 'run-a',
  missionId: 'mission-a',
  recordType: 'call',
  recordId: null,
  newDraftId: null,
  scope: 'between_legs',
  legId: null,
  previousLegId: 'leg-1',
  nextLegId: 'leg-2',
  correctionVersion: null,
};
const input = () => ({
  ...callDraft(undefined, 'planned', 'mission-a'),
  scope: 'between_legs' as const,
  payload: {
    ...callDraft(undefined, 'planned', 'mission-a').payload,
    previous_leg_id: 'leg-1',
    next_leg_id: 'leg-2',
  },
});
const identity = JSON.stringify(['store-a', 'epoch-a', 'simulation', 'run-a']);

describe('unsent workspace draft ownership', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('two_new_calls_have_distinct_ids', () => {
    const registry = new DraftRegistry(sessionStorage);
    const first = registry.createDraft(target, input());
    const second = registry.createDraft(target, input());
    expect(first.draftId).not.toBe(second.draftId);
    expect(first.target.newDraftId).toBe(first.draftId);
    expect(new DraftRegistry(sessionStorage).listDrafts()).toHaveLength(2);
  });

  it('migrates_transport_editor_choices_and_quarantines_other_identity', () => {
    const key = transportDraftKey(identity, 'mission-a');
    const legacy = newTransportDraft('mission-a');
    legacy.replacement_check_row_ids = ['row-1'];
    sessionStorage.setItem(key, JSON.stringify(legacy));
    const other = transportDraftKey(
      JSON.stringify(['other', 'epoch-a', 'simulation', 'run-a']),
      'mission-a'
    );
    sessionStorage.setItem(other, JSON.stringify(legacy));
    const result = recoverLegacyDrafts(sessionStorage, identity);
    expect(result.migratedDraftIds).toHaveLength(1);
    const recovered = new DraftRegistry(sessionStorage).resumeDraft(
      result.migratedDraftIds[0]
    )!;
    expect(recovered.input).toEqual(legacy.input);
    expect(recovered.editorState?.replacement_check_row_ids).toEqual(['row-1']);
    expect(result.quarantinedKeys).toContain(other);
    expect(sessionStorage.getItem(other)).not.toBeNull();
  });

  it('mission_scope_switch_keeps_target', () => {
    const registry = new DraftRegistry(sessionStorage);
    const draft = registry.createDraft(target, input());
    registry.createDraft(
      { ...target, missionId: 'mission-b' },
      { ...input(), mission_id: 'mission-b' }
    );
    expect(registry.resumeDraft(draft.draftId)?.target).toEqual({
      ...target,
      newDraftId: draft.draftId,
    });
    // Caller edits must never mutate the stored identity or parked input.
    draft.target.missionId = 'mutated';
    draft.input.payload.title = 'mutated';
    expect(registry.resumeDraft(draft.draftId)?.target.missionId).toBe(
      'mission-a'
    );
    expect(registry.resumeDraft(draft.draftId)?.input.payload.title).not.toBe(
      'mutated'
    );
  });

  it('corrupt_or_full_storage_retains_memory', () => {
    const registry = new DraftRegistry(sessionStorage);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    const draft = registry.createDraft(target, input());
    expect(draft.persistence.state).toBe('memory_only');
    expect(registry.resumeDraft(draft.draftId)?.input).toEqual(input());
    expect(draft.persistence.message).toContain('Keep this tab open');
    vi.restoreAllMocks();
    sessionStorage.setItem('operator-workspace-draft:v1:broken', '{');
    const recovered = new DraftRegistry(sessionStorage);
    expect(recovered.recoveryErrors()).toHaveLength(1);
    expect(sessionStorage.getItem('operator-workspace-draft:v1:broken')).toBe(
      '{'
    );
  });

  it('edited_after_submit_keeps_new_revision', () => {
    const registry = new DraftRegistry(sessionStorage);
    const draft = registry.createDraft(target, input());
    const edited = registry.editDraft(draft.draftId, {
      ...input(),
      payload: { ...input().payload, title: 'new edit' },
    });
    expect(edited?.revision).toBe(2);
    registry.retireSubmitted(draft.draftId, draft.revision);
    expect(registry.resumeDraft(draft.draftId)?.input.payload.title).toBe(
      'new edit'
    );
    registry.retireSubmitted(draft.draftId, 2);
    expect(registry.resumeDraft(draft.draftId)).toBeNull();
  });

  it('failed_retirement_exposes_error_and_keeps_recoverable_input', () => {
    const registry = new DraftRegistry(sessionStorage);
    const draft = registry.createDraft(target, input());
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(registry.discardDraft(draft.draftId).state).toBe('memory_only');
    expect(registry.resumeDraft(draft.draftId)?.persistence.message).toContain(
      'could not be cleared'
    );
  });

  it('legacy_pending_is_not_an_unsent_draft', () => {
    const key = 'operator-367-pending:mission-a:call';
    const raw = JSON.stringify({
      identity,
      command: { operation: 'create', body: input() },
      key: 'frozen-key',
    });
    sessionStorage.setItem(key, raw);
    const result = recoverLegacyDrafts(sessionStorage, identity);
    expect(result.migratedDraftIds).toEqual([]);
    expect(result.quarantinedKeys).toContain(key);
    expect(sessionStorage.getItem(key)).toBe(raw);
  });

  it('legacy_correction_keeps_full_target_and_deduplicates_repeated_recovery', () => {
    const key =
      'operator-367-draft:' +
      JSON.stringify({
        storeId: 'store-a',
        epoch: 'epoch-a',
        sourceMode: 'simulation',
        simulationRunId: 'run-a',
        missionId: 'mission-a',
        recordId: 'record-a:correction:3',
      });
    const issue = {
      ...input(),
      record_type: 'issue',
      payload: { ...input().payload, entry_type: 'issue', status: 'resolved' },
    };
    sessionStorage.setItem(
      key,
      JSON.stringify({
        input: issue,
        version: 5,
        text: 'corrected text',
        at: '2026-10-17T15:00:00Z',
      })
    );
    const result = recoverLegacyDrafts(sessionStorage, identity);
    expect(result.errors).toEqual([]);
    expect(result.migratedDraftIds).toHaveLength(1);
    const recovered = new DraftRegistry(sessionStorage).resumeDraft(
      result.migratedDraftIds[0]
    )!;
    expect(recovered.target).toMatchObject({
      ...target,
      recordType: 'issue',
      recordId: 'record-a',
      correctionVersion: 3,
    });
    expect(recovered.baseVersion).toBe(5);
    expect(recovered.editorState).toMatchObject({
      text: 'corrected text',
      at: '2026-10-17T15:00:00Z',
    });
    expect(sessionStorage.getItem(key)).toBeNull();
    expect(
      recoverLegacyDrafts(sessionStorage, identity).migratedDraftIds
    ).toEqual([]);
  });

  it('legacy_write_failure_does_not_delete_original_and_repeated_scan_is_idempotent', () => {
    const key =
      'operator-367-draft:' +
      JSON.stringify({
        storeId: 'store-a',
        epoch: 'epoch-a',
        sourceMode: 'simulation',
        simulationRunId: 'run-a',
        missionId: 'mission-a',
        recordId: 'new',
      });
    sessionStorage.setItem(
      key,
      JSON.stringify({ input: input(), baseVersion: null })
    );
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    const registry = new DraftRegistry(sessionStorage);
    const failed = recoverLegacyDrafts(sessionStorage, identity, registry);
    expect(failed.errors).toHaveLength(1);
    expect(sessionStorage.getItem(key)).not.toBeNull();
    expect(registry.listDrafts()).toHaveLength(1);
    vi.restoreAllMocks();
    const retried = recoverLegacyDrafts(sessionStorage, identity, registry);
    expect(retried.errors).toEqual([]);
    expect(registry.listDrafts()).toHaveLength(1);
  });

  it('recognizes_real_legacy_new_issue_and_capability_markers', () => {
    for (const [recordId, recordType, entryType] of [
      ['new-issue', 'issue', 'issue'],
      ['new-capability', 'journal_entry', 'capability_assessment'],
    ]) {
      const key =
        'operator-367-draft:' +
        JSON.stringify({
          storeId: 'store-a',
          epoch: 'epoch-a',
          sourceMode: 'simulation',
          simulationRunId: 'run-a',
          missionId: 'mission-a',
          recordId,
        });
      sessionStorage.setItem(
        key,
        JSON.stringify({
          input: {
            ...input(),
            record_type: recordType,
            payload: { ...input().payload, entry_type: entryType },
          },
          version: null,
        })
      );
    }
    const result = recoverLegacyDrafts(sessionStorage, identity);
    expect(result.migratedDraftIds).toHaveLength(2);
    for (const id of result.migratedDraftIds)
      expect(
        new DraftRegistry(sessionStorage).resumeDraft(id)?.target.recordId
      ).toBeNull();
  });

  it('duplicate_legacy_keys_produce_one_draft_and_failed_key_retirement_is_recoverable', () => {
    const legacy = {
      storeId: 'store-a',
      epoch: 'epoch-a',
      sourceMode: 'simulation',
      simulationRunId: 'run-a',
      missionId: 'mission-a',
      recordId: 'new',
    };
    const keys = [
      'operator-367-draft:' + JSON.stringify(legacy),
      'operator-367-draft:' + JSON.stringify(legacy, null, 1),
    ];
    keys.forEach((key) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({ input: input(), baseVersion: null })
      )
    );
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(recoverLegacyDrafts(sessionStorage, identity).errors).toHaveLength(
      2
    );
    expect(new DraftRegistry(sessionStorage).listDrafts()).toHaveLength(1);
    vi.restoreAllMocks();
    expect(
      recoverLegacyDrafts(sessionStorage, identity).migratedDraftIds
    ).toHaveLength(1);
    expect(keys.map((key) => sessionStorage.getItem(key))).toEqual([
      null,
      null,
    ]);
  });
});
