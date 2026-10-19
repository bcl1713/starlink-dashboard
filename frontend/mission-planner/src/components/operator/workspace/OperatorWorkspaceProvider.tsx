import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  useOperatorJournal,
  type Pending,
} from '@/hooks/api/useOperatorJournal';
import {
  operatorIdentity,
  useOperatorHealth,
} from '@/hooks/api/operatorReadSession';
import { readOperatorRecords } from '@/services/operator';
import type { CommandReceipt, OperatorCommand } from '@/types/operator';
import { createClientId } from '@/lib/clientId';
import { DraftRegistry, getDraftRegistry } from './draftRegistry';
import {
  assertCommandTarget,
  commandLane,
  draftCommand,
  loadPendingOwners,
  pendingPrefix,
  targetIdentity,
  type PendingEnvelope,
  type TransactionTrayItem,
  type CommandAttempt,
} from './commandRegistry';
import type { DraftTarget } from './types';
import { recoverLegacyDrafts } from './legacyRecovery';

type JournalOwner = ReturnType<typeof useOperatorJournal>;
type SubmitOptions = {
  command?: OperatorCommand;
  atCurrentTime?: (asOf: string) => OperatorCommand;
  captureCurrentTime?: boolean;
  captureDimensions?: ('functional' | 'redundancy')[];
};
interface Workspace {
  ownsHealth: boolean;
  registry: DraftRegistry;
  selectedDraftId: string | null;
  openDraft: (draftId: string) => void;
  closeEditor: () => void;
  submitDraft: (draftId: string, options?: SubmitOptions) => Promise<void>;
  retryExact: (commandId: string) => Promise<void>;
  rereadAndReconcile: (commandId: string) => Promise<void>;
  tray: TransactionTrayItem[];
  busyLanes: readonly string[];
  attempts: readonly CommandAttempt[];
  recoveryErrors: string[];
  refreshDrafts: () => void;
}
const Context = createContext<Workspace | null>(null);

function Owner({
  lane,
  target,
  register,
  publish,
  receipt,
  attempt,
}: {
  lane: string;
  target: DraftTarget;
  register: (lane: string, api: JournalOwner) => void;
  publish: (lane: string, api: JournalOwner) => void;
  receipt: (lane: string, request: Pending, value: CommandReceipt) => void;
  attempt: (request: Pending) => void;
}) {
  const api = useOperatorJournal(
    target.missionId,
    target.recordType as Parameters<typeof useOperatorJournal>[1],
    {
      pendingStorageKey: pendingPrefix + lane,
      requirePersistence: true,
      readRecords: false,
      healthPolling: false,
      onReceipt: (request, value) => receipt(lane, request, value),
      onAttempt: attempt,
    }
  );
  useLayoutEffect(() => {
    register(lane, api);
  });
  useEffect(
    () => {
      publish(lane, api);
    },
    // Function identities change with the parent; only transaction state publishes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      api.pending,
      api.saving,
      api.saved,
      api.blocked,
      api.error,
      api.storageError,
      api.reconcileError,
      api.latest,
      api.identity,
      api.health.data?.ready,
      api.health.isError,
    ]
  );
  return null;
}

export function OperatorWorkspaceProvider({
  children,
  registry: supplied,
}: {
  children: ReactNode;
  registry?: DraftRegistry;
}) {
  const [registry] = useState(() => supplied ?? getDraftRegistry());
  const [restored] = useState(() => {
    try {
      return loadPendingOwners(sessionStorage);
    } catch {
      return loadPendingOwners(null);
    }
  });
  const [owners, setOwners] = useState(
    () =>
      new Map(
        restored.requests.map((p) => [
          commandLane(p.workspace.target),
          p.workspace.target,
        ])
      )
  );
  const [tray, setTray] = useState<TransactionTrayItem[]>(() =>
    restored.requests.map((p) => ({
      lane: commandLane(p.workspace.target),
      commandId: p.key,
      draftId: p.workspace.draftId,
      submittedRevision: p.workspace.revision,
      target: p.workspace.target,
      title:
        registry.resumeDraft(p.workspace.draftId)?.input.payload.title ??
        'Retained save',
      status: 'uncertain',
      message: 'Receipt uncertain. Review before retrying the same save.',
      pending: p,
      retryReady: false,
    }))
  );
  const [attempts, setAttempts] = useState<CommandAttempt[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [migrationErrors, setMigrationErrors] = useState<string[]>([]);
  const scannedIdentities = useRef(new Set<string>());
  const [, refreshDrafts] = useState(0);
  const client = useQueryClient();
  const location = useLocation();
  const active =
    location.pathname === '/operator' &&
    new URLSearchParams(location.search).get('workspace') === '1';
  const ownsHealth =
    active ||
    tray.some(
      (t) =>
        !!t.pending ||
        ['saving', 'uncertain', 'needs_review'].includes(t.status)
    );
  const health = useOperatorHealth(ownsHealth);
  const identity = operatorIdentity(health.data);
  useEffect(() => {
    if (!active || !identity || scannedIdentities.current.has(identity)) return;
    scannedIdentities.current.add(identity);
    try {
      const result = recoverLegacyDrafts(sessionStorage, identity, registry);
      setMigrationErrors([
        ...result.errors.map((error) => error.message),
        ...(result.quarantinedKeys.length
          ? [
              'Older or ambiguous drafts/saves remain in recovery. Open the previous workspace to review them; they have not been sent.',
            ]
          : []),
      ]);
      refreshDrafts((n) => n + 1);
    } catch {
      setMigrationErrors([
        'Legacy draft storage unavailable. Keep this tab open.',
      ]);
    }
  }, [active, identity, registry]);
  const apis = useRef(new Map<string, JournalOwner>());
  const waiters = useRef(new Map<string, ((api: JournalOwner) => void)[]>());
  const busy = useRef(new Set<string>());
  const [busyLanes, setBusyLanes] = useState<string[]>([]);
  const trayRef = useRef(tray);
  trayRef.current = tray;

  function update(lane: string, patch: Partial<TransactionTrayItem>) {
    setTray((rows) =>
      rows.map((row) => (row.lane === lane ? { ...row, ...patch } : row))
    );
  }
  function register(lane: string, api: JournalOwner) {
    apis.current.set(lane, api);
    waiters.current.get(lane)?.forEach((resolve) => resolve(api));
    waiters.current.delete(lane);
  }
  function publish(lane: string, api: JournalOwner) {
    const pending = api.pending?.workspace
      ? (api.pending as PendingEnvelope)
      : undefined;
    const row = trayRef.current.find((row) => row.lane === lane);
    if (!row) return;
    const message =
      api.storageError ??
      api.reconcileError ??
      api.error?.message ??
      row.message;
    const retryReady =
      !!pending &&
      pending.identity === api.identity &&
      api.health.data?.ready === true &&
      !api.health.isError &&
      !api.blocked &&
      !api.saving &&
      !api.storageError;
    const publishRow = (patch: Partial<TransactionTrayItem>) =>
      update(lane, { ...patch, retryReady });
    if (api.blocked)
      publishRow({
        status:
          api.error?.code === 'epoch_mismatch' ? 'quarantined' : 'needs_review',
        message,
        pending,
      });
    else if (api.storageError)
      publishRow({ status: 'storage_error', message, pending });
    else if (api.saving)
      publishRow({
        status: 'saving',
        message: null,
        pending,
        ...(pending ? { commandId: pending.key } : {}),
      });
    else if (pending)
      publishRow({
        status: 'uncertain',
        commandId: pending.key,
        message,
        pending,
      });
    else if (api.error)
      publishRow({ status: 'failed', message, pending: undefined });
    else if (row.retryReady !== retryReady) publishRow({});
  }
  function observeAttempt(request: Pending) {
    const observed = {
      id: createClientId(),
      request: structuredClone(request),
    };
    setAttempts((previous) => [...previous.slice(-99), observed]);
  }
  function receipt(lane: string, request: Pending, value: CommandReceipt) {
    if (request.workspace)
      void client.invalidateQueries({
        queryKey: [
          'operator-events',
          request.workspace.target.missionId,
          request.identity,
        ],
      });
    if (request.workspace)
      registry.retireSubmitted(
        request.workspace.draftId,
        request.workspace.revision
      );
    update(lane, {
      receipt: value,
      commandId: request.key,
      status: 'accepted_unreadable',
      pending: undefined,
      message: 'Save accepted. Reading current saved state…',
    });
    refreshDrafts((n) => n + 1);
  }
  async function ensureOwner(target: DraftTarget): Promise<JournalOwner> {
    const lane = commandLane(target);
    const current = apis.current.get(lane);
    if (current) return current;
    const ready = new Promise<JournalOwner>((resolve) => {
      waiters.current.set(lane, [
        ...(waiters.current.get(lane) ?? []),
        resolve,
      ]);
    });
    setOwners((previous) => new Map(previous).set(lane, target));
    return ready;
  }
  async function submitDraft(draftId: string, options: SubmitOptions = {}) {
    const draft = registry.resumeDraft(draftId);
    if (!draft) return;
    const lane = commandLane(draft.target);
    const previous = trayRef.current.find((row) => row.lane === lane);
    if (
      busy.current.has(lane) ||
      previous?.pending ||
      previous?.status === 'saving' ||
      previous?.status === 'quarantined'
    )
      return;
    busy.current.add(lane);
    setBusyLanes([...busy.current]);
    setTray((rows) => [
      ...rows.filter((row) => row.lane !== lane),
      {
        lane,
        commandId: lane,
        draftId,
        submittedRevision: draft.revision,
        target: draft.target,
        title: draft.input.payload.title,
        status: 'saving',
        message: null,
      },
    ]);
    try {
      if (operatorIdentity(health.data) !== targetIdentity(draft.target)) {
        update(lane, {
          status: 'quarantined',
          message: 'Store changed. Reread before submitting this draft.',
        });
        return;
      }
      const api = await ensureOwner(draft.target);
      const command = options.atCurrentTime
        ? options.atCurrentTime(
            (
              await readOperatorRecords({
                mission_id: draft.target.missionId,
                record_type: draft.target.recordType,
              })
            ).as_of
          )
        : (options.command ?? draftCommand(draft));
      assertCommandTarget(draft, command);
      api.openEditor(draft.baseRecord ?? undefined);
      const result = await api.save(command, {
        captureCurrentTime: options.captureCurrentTime,
        captureDimensions: options.captureDimensions,
        workspace: {
          schemaVersion: 1,
          draftId,
          revision: draft.revision,
          baseVersion: draft.baseVersion,
          target: draft.target,
        },
      });
      if (result)
        update(lane, {
          status: result.current ? 'accepted' : 'accepted_unreadable',
          pending: undefined,
          retryReady: false,
          receipt: result.receipt,
          current: result.current,
          message: result.current
            ? null
            : 'Save accepted. Current saved state could not be read.',
        });
    } catch (error) {
      update(lane, {
        status: 'failed',
        message:
          error instanceof Error
            ? error.message
            : 'Save could not be prepared.',
      });
    } finally {
      busy.current.delete(lane);
      setBusyLanes([...busy.current]);
    }
  }
  async function retryExact(commandId: string) {
    const row = trayRef.current.find((row) => row.commandId === commandId);
    if (!row || busy.current.has(row.lane) || !row.retryReady) return;
    busy.current.add(row.lane);
    setBusyLanes([...busy.current]);
    try {
      const api = await ensureOwner(row.target);
      const result = await api.retry();
      if (result)
        update(row.lane, {
          status: result.current ? 'accepted' : 'accepted_unreadable',
          pending: undefined,
          retryReady: false,
          receipt: result.receipt,
          current: result.current,
          message: result.current
            ? null
            : 'Save accepted. Current saved state could not be read.',
        });
    } finally {
      busy.current.delete(row.lane);
      setBusyLanes([...busy.current]);
    }
  }
  async function rereadAndReconcile(commandId: string) {
    const row = trayRef.current.find((row) => row.commandId === commandId);
    if (!row) return;
    const api = await ensureOwner(row.target);
    const result = await api.reconcile();
    if (result)
      update(row.lane, {
        status: row.receipt ? 'accepted' : 'needs_review',
        current: result.current,
        message:
          'Saved state reread. Review your retained input before submitting another command.',
        pending: undefined,
      });
  }
  return (
    <Context.Provider
      value={{
        registry,
        selectedDraftId,
        openDraft: (draftId) => {
          if (registry.resumeDraft(draftId)) setSelectedDraftId(draftId);
        },
        closeEditor: () => setSelectedDraftId(null),
        submitDraft,
        ownsHealth,
        retryExact,
        rereadAndReconcile,
        tray,
        busyLanes,
        attempts,
        recoveryErrors: [
          ...restored.errors,
          ...migrationErrors,
          ...registry.recoveryErrors().map((e) => e.message),
        ],
        refreshDrafts: () => refreshDrafts((n) => n + 1),
      }}
    >
      {children}
      {[...owners].map(([lane, target]) => (
        <Owner
          key={lane}
          lane={lane}
          target={target}
          register={register}
          publish={publish}
          receipt={receipt}
          attempt={observeAttempt}
        />
      ))}
    </Context.Provider>
  );
}

// The paired hook is the public API for this persistent provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useOperatorWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error('Operator workspace provider is required.');
  return value;
}
