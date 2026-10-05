import {
  parseOverviewDisplayMessage,
  type CommandFeedback,
  type DisplayAction,
  type DisplayPeer,
  type DisplayResult,
  type DisplaySnapshot,
  type OverviewDisplayMessage,
} from './overview-display-protocol';

export type DisplaySessionOptions = {
  onSnapshot(snapshot: DisplaySnapshot): void;
} & (
  | { role: 'controller' }
  | {
      role: 'display';
      readPeer(): Omit<DisplayPeer, 'id' | 'label'>;
      onCommand(
        action: DisplayAction,
        expiresAtMs: number
      ): Promise<DisplayResult>;
    }
);
export interface OverviewDisplaySession {
  readonly id: string;
  readonly label: string;
  request(targetId: string, action: DisplayAction): string | null;
  publishPresence(): void;
  close(): void;
}

type Outgoing = OverviewDisplayMessage extends infer Message
  ? Message extends OverviewDisplayMessage
    ? Omit<Message, 'v' | 'sender' | 'seq'>
    : never
  : never;
type Command = Extract<OverviewDisplayMessage, { type: 'command' }>;
type Result = Extract<OverviewDisplayMessage, { type: 'result' }>;

const HEARTBEAT_MS = 5000;
const PEER_TTL_MS = 15000;
const COMMAND_TTL_MS = 3000;

function createId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // getRandomValues also works where randomUUID's secure-context API is absent.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, '0')
  ).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function createOverviewDisplaySession(
  options: DisplaySessionOptions
): OverviewDisplaySession {
  const id = createId();
  const label = `Overview ${id.slice(-6)}`;
  let channel: BroadcastChannel | null = null;
  let scheduler: ReturnType<typeof setInterval> | null = null;
  let available = false;
  let closed = false;
  let seq = 0;
  let lastHeartbeat = Date.now();
  let feedback: CommandFeedback | null = null;
  let pendingDeadline: number | null = null;
  const peers = new Map<string, { peer: DisplayPeer; seenAt: number }>();
  const peerSeq = new Map<string, number>();
  const commands = new Map<string, { result: Outgoing | null }>();

  function emit() {
    options.onSnapshot({
      available,
      peers: [...peers.values()].map(({ peer }) => ({
        ...peer,
        actions: [...peer.actions],
      })),
      feedback: feedback && { ...feedback },
    });
  }
  function release() {
    if (scheduler !== null) clearInterval(scheduler);
    scheduler = null;
    if (channel) {
      channel.removeEventListener('message', receive);
      channel.removeEventListener('messageerror', transportFailed);
      try {
        channel.close();
      } catch {
        /* Best-effort transport cleanup. */
      }
    }
    channel = null;
    pendingDeadline = null;
    commands.clear();
    peers.clear();
    peerSeq.clear();
  }
  function transportFailed() {
    if (closed) return;
    available = false;
    if (feedback?.status === 'pending')
      feedback = { ...feedback, status: 'unavailable' };
    release();
    emit();
  }
  function send(message: Outgoing): boolean {
    if (closed || !available || !channel) return false;
    try {
      channel.postMessage({ ...message, v: 1, sender: id, seq: ++seq });
      return true;
    } catch {
      transportFailed();
      return false;
    }
  }
  function presence(target: string | null) {
    if (options.role !== 'display' || closed || !available) return;
    send({ type: 'presence', target, label, ...options.readPeer() });
  }
  function expire(now: number): boolean {
    let changed = false;
    for (const [peerId, { seenAt }] of peers) {
      if (now - seenAt < PEER_TTL_MS) continue;
      peers.delete(peerId);
      if (feedback?.status === 'pending' && feedback.targetId === peerId) {
        feedback = { ...feedback, status: 'unavailable' };
        pendingDeadline = null;
      }
      changed = true;
    }
    if (
      pendingDeadline !== null &&
      now >= pendingDeadline &&
      feedback?.status === 'pending'
    ) {
      feedback = { ...feedback, status: 'timeout' };
      pendingDeadline = null;
      changed = true;
    }
    return changed;
  }
  async function execute(message: Command) {
    if (options.role !== 'display') return;
    const key = JSON.stringify([message.sender, message.requestId]);
    const previous = commands.get(key);
    if (previous) {
      if (previous.result) send(previous.result);
      return;
    }
    const entry = { result: null as Outgoing | null };
    commands.set(key, entry);
    if (commands.size > 128) commands.delete(commands.keys().next().value!);
    let status: DisplayResult;
    if (Date.now() >= message.expiresAtMs) status = 'expired';
    else if (!options.readPeer().actions.includes(message.action))
      status = 'unsupported';
    else {
      try {
        status = await options.onCommand(message.action, message.expiresAtMs);
      } catch {
        status = 'failed';
      }
      // No late callback completion may be reported as success.
      if (Date.now() >= message.expiresAtMs) status = 'expired';
    }
    if (closed || !available) return;
    entry.result = {
      type: 'result',
      target: message.sender,
      requestId: message.requestId,
      action: message.action,
      status,
    };
    send(entry.result);
  }
  function acceptResult(message: Result) {
    if (
      !feedback ||
      feedback.status !== 'pending' ||
      message.requestId !== feedback.requestId ||
      message.sender !== feedback.targetId ||
      message.action !== feedback.action
    )
      return;
    if (expire(Date.now())) emit();
    if (feedback.status !== 'pending') return;
    feedback = { ...feedback, status: message.status };
    pendingDeadline = null;
    const peer = peers.get(message.sender);
    if (peer && message.seq > (peerSeq.get(message.sender) ?? 0)) {
      peerSeq.set(message.sender, message.seq);
    }
    emit();
  }
  function receive(event: MessageEvent<unknown>) {
    if (closed || !available) return;
    const message = parseOverviewDisplayMessage(event.data);
    if (
      !message ||
      message.sender === id ||
      (message.target !== null && message.target !== id)
    )
      return;
    if (options.role === 'display') {
      if (message.type === 'discover') presence(message.sender);
      else if (message.type === 'command') void execute(message);
      return;
    }
    if (message.type === 'presence' || message.type === 'bye') {
      if (message.seq <= (peerSeq.get(message.sender) ?? 0)) return;
      peerSeq.set(message.sender, message.seq);
      if (message.type === 'presence') {
        peers.set(message.sender, {
          peer: {
            id: message.sender,
            label: message.label,
            actions: message.actions,
          },
          seenAt: Date.now(),
        });
      } else {
        peers.delete(message.sender);
        if (
          feedback?.status === 'pending' &&
          feedback.targetId === message.sender
        ) {
          feedback = { ...feedback, status: 'unavailable' };
          pendingDeadline = null;
        }
      }
      emit();
    } else if (message.type === 'result') acceptResult(message);
  }

  const session: OverviewDisplaySession = {
    id,
    label,
    request(targetId, action) {
      if (options.role !== 'controller' || closed || !available) return null;
      expire(Date.now());
      const requestId = createId();
      const peer = peers.get(targetId);
      if (!peer || !peer.peer.actions.includes(action)) {
        feedback = { requestId, targetId, action, status: 'unavailable' };
        pendingDeadline = null;
        emit();
        return null;
      }
      feedback = { requestId, targetId, action, status: 'pending' };
      pendingDeadline = Date.now() + COMMAND_TTL_MS;
      emit();
      return send({
        type: 'command',
        target: targetId,
        requestId,
        action,
        expiresAtMs: pendingDeadline,
      })
        ? requestId
        : null;
    },
    publishPresence() {
      presence(null);
    },
    close() {
      if (closed) return;
      closed = true;
      // Departure is best effort; disposal never calls an unmounted subscriber.
      if (available && channel) {
        try {
          channel.postMessage({
            v: 1,
            type: 'bye',
            sender: id,
            target: null,
            seq: ++seq,
          });
        } catch {
          /* The resources below must still be released. */
        }
      }
      available = false;
      feedback = null;
      release();
    },
  };
  try {
    channel = new BroadcastChannel('starlink-overview-display-v1');
    channel.addEventListener('message', receive);
    channel.addEventListener('messageerror', transportFailed);
    available = true;
    scheduler = setInterval(() => {
      if (expire(Date.now())) emit();
      if (
        options.role === 'display' &&
        Date.now() - lastHeartbeat >= HEARTBEAT_MS
      ) {
        lastHeartbeat = Date.now();
        presence(null);
      }
    }, 1000);
  } catch {
    transportFailed();
    return session;
  }
  emit();
  if (options.role === 'controller') send({ type: 'discover', target: null });
  else presence(null);
  return session;
}
