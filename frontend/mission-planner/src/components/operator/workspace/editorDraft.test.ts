/** @vitest-environment jsdom */
import { afterEach, expect, it } from 'vitest';
import { health, record } from '@/test/operator-fixtures';
import { callDraft } from '../callDraft';
import { participationDraft } from '../conferenceCommands';
import { issueInput } from '../issueForms';
import { newTransportDraft } from '../transportForms';
import { createEditorDraft } from './editorDraft';
import { DraftRegistry } from './draftRegistry';
import { draftCommand } from './commandRegistry';
import type { OperatorInput, SavedRecord } from '@/types/operator';

afterEach(() => sessionStorage.clear());
it.each([
  ['call', callDraft(undefined, 'planned', 'mission-a')],
  ['participation', participationDraft('mission-a')],
  ['issue', issueInput('mission-a')],
  ['transport_decision', newTransportDraft('mission-a').input],
] as const)(
  'opens an existing %s editor with the immutable saved base before its first persistence',
  (kind, input) => {
    const saved = {
      ...record,
      ...input,
      record_type: kind,
      record_id: `existing-${kind}`,
      version: 7,
    } as SavedRecord;
    const edited = {
      ...input,
      payload: { ...input.payload, title: 'Edited existing record' },
    } as OperatorInput;
    const registry = new DraftRegistry(sessionStorage);
    const draft = createEditorDraft(registry, health, edited, saved);
    const restored = new DraftRegistry(sessionStorage).resumeDraft(
      draft.draftId
    )!;
    expect(restored.baseRecord).toEqual(saved);
    expect(restored.baseVersion).toBe(7);
    expect(restored.target.recordId).toBe(saved.record_id);
    expect(draftCommand(restored)).toMatchObject({
      operation: 'update',
      record_id: saved.record_id,
      body: { expected_version: 7 },
    });
  }
);
