import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createOverviewDisplaySession,
  type OverviewDisplaySession,
} from './overview-display-session';
import type {
  DisplayResult,
  DisplaySnapshot,
  OverviewDisplayMessage,
} from './overview-display-protocol';

// The transport double preserves separate senders, asynchronous FIFO delivery,
// no self delivery and captured recipients, without replacing session behavior.
class MemoryChannel {
  static instances: MemoryChannel[] = [];
  static sent: OverviewDisplayMessage[] = [];
  static queue: (() => void)[] = [];
  static paused = false;
  static failPost = false;
  static failConstructor = false;
  listeners = new Map<string, Set<EventListener>>();
  closed = false;
  readonly name: string;
  constructor(name: string) {
    this.name = name;
    if (MemoryChannel.failConstructor) throw new Error('constructor failed');
    MemoryChannel.instances.push(this);
  }
  addEventListener(type: string, listener: EventListener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: EventListener) {
    this.listeners.get(type)?.delete(listener);
  }
  postMessage(message: OverviewDisplayMessage) {
    if (MemoryChannel.failPost) throw new Error('post failed');
    MemoryChannel.sent.push(structuredClone(message));
    for (const recipient of MemoryChannel.instances) {
      if (
        recipient === this ||
        recipient.closed ||
        recipient.name !== this.name
      )
        continue;
      const cloned = structuredClone(message);
      MemoryChannel.queue.push(() => {
        if (!recipient.closed) recipient.deliver(cloned);
      });
    }
  }
  deliver(value: unknown) {
    for (const listener of this.listeners.get('message') ?? [])
      listener(new MessageEvent('message', { data: value }));
  }
  close() {
    this.closed = true;
  }
  static async flush() {
    if (this.paused) return;
    // Drain callbacks and async command continuations in delivery order.
    for (let i = 0; i < 10; i++) {
      while (this.queue.length) this.queue.shift()!();
      await Promise.resolve();
    }
  }
}

let sessions: OverviewDisplaySession[];
function controller() {
  let snapshot: DisplaySnapshot = {
    available: false,
    peers: [],
    feedback: null,
  };
  const updates: DisplaySnapshot[] = [];
  const session = createOverviewDisplaySession({
    role: 'controller',
    onSnapshot: (next) => {
      snapshot = next;
      updates.push(next);
    },
  });
  sessions.push(session);
  return {
    session,
    get snapshot() {
      return snapshot;
    },
    updates,
  };
}
function display(
  onCommand = vi.fn(async (): Promise<DisplayResult> => 'accepted')
) {
  const peer = {
    fullscreen: false,
    actions: ['recenter', 'fullscreen'] as ('recenter' | 'fullscreen')[],
  };
  const onSnapshot = vi.fn();
  const session = createOverviewDisplaySession({
    role: 'display',
    readPeer: () => peer,
    onCommand,
    onSnapshot,
  });
  sessions.push(session);
  return { session, peer, onCommand, onSnapshot };
}
function latest(type: OverviewDisplayMessage['type']) {
  return MemoryChannel.sent.filter((message) => message.type === type).at(-1)!;
}
function rawPresence(sender: string, seq = 100) {
  return {
    v: 1,
    type: 'presence',
    sender,
    target: null,
    seq,
    label: 'Overview raw',
    fullscreen: false,
    actions: ['recenter', 'fullscreen'],
  };
}
function deliverController(value: unknown) {
  MemoryChannel.instances.find((channel) => !channel.closed)!.deliver(value);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(0);
  vi.stubGlobal('BroadcastChannel', MemoryChannel);
  MemoryChannel.instances = [];
  MemoryChannel.sent = [];
  MemoryChannel.queue = [];
  MemoryChannel.paused = false;
  MemoryChannel.failPost = false;
  MemoryChannel.failConstructor = false;
  sessions = [];
});
afterEach(() => {
  for (const session of sessions) session.close();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('Overview display discovery and lifecycle', () => {
  it('discovers an existing display and uses its matching human-visible label', async () => {
    const host = display();
    const control = controller();
    await MemoryChannel.flush();
    expect(control.snapshot).toEqual({
      available: true,
      peers: [{ id: host.session.id, label: host.session.label, ...host.peer }],
      feedback: null,
    });
    expect(host.session.id).toMatch(
      /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i
    );
    expect(host.session.label).toBe(`Overview ${host.session.id.slice(-6)}`);
    expect(
      MemoryChannel.instances.every(
        (channel) => channel.name === 'starlink-overview-display-v1'
      )
    ).toBe(true);
  });

  it('discovers a display started after the controller and publishes actual state every five seconds', async () => {
    const control = controller();
    const host = display();
    await MemoryChannel.flush();
    expect(control.snapshot.peers).toHaveLength(1);
    host.peer.fullscreen = true;
    await vi.advanceTimersByTimeAsync(4999);
    await MemoryChannel.flush();
    expect(control.snapshot.peers[0].fullscreen).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await MemoryChannel.flush();
    expect(control.snapshot.peers[0].fullscreen).toBe(true);
    expect(
      MemoryChannel.sent.filter((message) => message.type === 'presence')
    ).toHaveLength(2);
  });

  it('multiple controllers get one targeted discover response each without rebroadcast loops', async () => {
    const host = display();
    const first = controller();
    const second = controller();
    await MemoryChannel.flush();
    expect(first.snapshot.peers.map((peer) => peer.id)).toEqual([
      host.session.id,
    ]);
    expect(second.snapshot.peers.map((peer) => peer.id)).toEqual([
      host.session.id,
    ]);
    expect(
      MemoryChannel.sent
        .filter((message) => message.type === 'presence')
        .map((message) => message.target)
    ).toEqual([null, first.session.id, second.session.id]);
    expect(MemoryChannel.sent).toHaveLength(5);
  });

  it('missing heartbeat expires peer after fifteen seconds', async () => {
    const control = controller();
    deliverController(rawPresence('silent-display'));
    await vi.advanceTimersByTimeAsync(14999);
    expect(control.snapshot.peers).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(control.snapshot.peers).toEqual([]);
    expect(control.session.request('silent-display', 'recenter')).toBeNull();
  });

  it('uses receive time rather than sequence values for expiry', async () => {
    const control = controller();
    deliverController(rawPresence('silent-display'));
    await vi.advanceTimersByTimeAsync(14000);
    deliverController(rawPresence('silent-display', 101));
    await vi.advanceTimersByTimeAsync(14000);
    expect(control.snapshot.peers).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(control.snapshot.peers).toEqual([]);
  });

  it('ignores decreasing/duplicate presence and does not let them renew stale capability', async () => {
    const control = controller();
    deliverController(rawPresence('silent-display'));
    await vi.advanceTimersByTimeAsync(10000);
    deliverController({
      ...rawPresence('silent-display', 99),
      fullscreen: true,
    });
    deliverController(rawPresence('silent-display'));
    expect(control.snapshot.peers[0].fullscreen).toBe(false);
    await vi.advanceTimersByTimeAsync(5000);
    expect(control.snapshot.peers).toEqual([]);
  });

  it('bye removes only its sender and makes its pending request unavailable', async () => {
    const control = controller();
    const host = display();
    const other = display();
    await MemoryChannel.flush();
    MemoryChannel.paused = true;
    control.session.request(host.session.id, 'recenter');
    host.session.close();
    MemoryChannel.paused = false;
    await MemoryChannel.flush();
    expect(control.snapshot.peers.map((peer) => peer.id)).toEqual([
      other.session.id,
    ]);
    expect(control.snapshot.feedback?.status).toBe('unavailable');
    expect(other.onCommand).not.toHaveBeenCalled();
  });

  it('ignores regressive bye and presence targeted to a different controller', () => {
    const control = controller();
    deliverController(rawPresence('a'));
    deliverController({
      v: 1,
      type: 'bye',
      sender: 'a',
      target: null,
      seq: 99,
    });
    deliverController({ ...rawPresence('b'), target: 'another-controller' });
    expect(control.snapshot.peers.map((peer) => peer.id)).toEqual(['a']);
  });

  it('cleanup is idempotent and returns channel listeners and timers to baseline', async () => {
    const baseline = vi.getTimerCount();
    const control = controller();
    const host = display();
    await MemoryChannel.flush();
    expect(vi.getTimerCount()).toBe(baseline + 2);
    control.session.request(host.session.id, 'recenter');
    const countBeforeClose = control.updates.length;
    for (const session of sessions) {
      session.close();
      session.close();
      session.publishPresence();
    }
    await MemoryChannel.flush();
    await vi.advanceTimersByTimeAsync(20000);
    expect(vi.getTimerCount()).toBe(baseline);
    expect(
      MemoryChannel.instances.every(
        (channel) =>
          channel.closed &&
          [...channel.listeners.values()].every((set) => set.size === 0)
      )
    ).toBe(true);
    expect(control.updates).toHaveLength(countBeforeClose);
    expect(host.onCommand).not.toHaveBeenCalled();
    expect(control.session.request(host.session.id, 'recenter')).toBeNull();
    expect(
      MemoryChannel.sent.filter((message) => message.type === 'bye')
    ).toHaveLength(2);
  });
});

describe('targeted commands and acknowledgments', () => {
  it('recenter reaches exactly the selected display', async () => {
    const control = controller();
    const selectedRecenter = vi.fn(
      async (): Promise<DisplayResult> => 'accepted'
    );
    const otherRecenter = vi.fn(async (): Promise<DisplayResult> => 'accepted');
    const selected = display(selectedRecenter);
    display(otherRecenter);
    await MemoryChannel.flush();
    const requestId = control.session.request(selected.session.id, 'recenter');
    expect(control.snapshot.feedback).toEqual({
      requestId,
      targetId: selected.session.id,
      action: 'recenter',
      status: 'pending',
    });
    await MemoryChannel.flush();
    expect(selectedRecenter).toHaveBeenCalledTimes(1);
    expect(selectedRecenter).toHaveBeenCalledWith('recenter', 3000);
    expect(otherRecenter).not.toHaveBeenCalled();
    expect(control.snapshot.feedback?.status).toBe('accepted');
    expect(selected.session.request(control.session.id, 'recenter')).toBeNull();
  });

  it('duplicate request does not execute again, including while callback is pending', async () => {
    let complete!: (result: DisplayResult) => void;
    const selectedRecenter = vi.fn(
      () =>
        new Promise<DisplayResult>((resolve) => {
          complete = resolve;
        })
    );
    const control = controller();
    const selected = display(selectedRecenter);
    await MemoryChannel.flush();
    control.session.request(selected.session.id, 'recenter');
    const command = latest('command');
    await MemoryChannel.flush();
    const hostChannel = MemoryChannel.instances[1];
    hostChannel.deliver(command);
    expect(selectedRecenter).toHaveBeenCalledTimes(1);
    complete('accepted');
    await MemoryChannel.flush();
    hostChannel.deliver(command);
    await MemoryChannel.flush();
    expect(selectedRecenter).toHaveBeenCalledTimes(1);
    expect(control.snapshot.feedback?.status).toBe('accepted');
  });

  it('late delivered command is expired', async () => {
    const control = controller();
    const host = display();
    await MemoryChannel.flush();
    MemoryChannel.paused = true;
    control.session.request(host.session.id, 'recenter');
    await vi.advanceTimersByTimeAsync(3000);
    MemoryChannel.paused = false;
    await MemoryChannel.flush();
    const expiredResult = latest('result');
    expect(expiredResult.type === 'result' && expiredResult.status).toBe(
      'expired'
    );
    expect(host.onCommand).not.toHaveBeenCalled();
    expect(control.snapshot.feedback?.status).toBe('timeout');
  });

  it('missing result times out after three seconds', async () => {
    const control = controller();
    deliverController(rawPresence('silent-display'));
    control.session.request('silent-display', 'recenter');
    await vi.advanceTimersByTimeAsync(3000);
    const snapshot = control.snapshot;
    expect(snapshot.feedback?.status).toBe('timeout');
  });

  it('late callback completion cannot replace timeout, while actual presence remains authoritative', async () => {
    let complete!: (result: DisplayResult) => void;
    const control = controller();
    const host = display(
      vi.fn(
        () =>
          new Promise<DisplayResult>((resolve) => {
            complete = resolve;
          })
      )
    );
    await MemoryChannel.flush();
    control.session.request(host.session.id, 'fullscreen');
    await MemoryChannel.flush();
    await vi.advanceTimersByTimeAsync(3000);
    host.peer.fullscreen = true;
    complete('accepted');
    await MemoryChannel.flush();
    expect(control.snapshot.feedback?.status).toBe('timeout');
    host.session.publishPresence();
    await MemoryChannel.flush();
    expect(control.snapshot.peers[0].fullscreen).toBe(true);
    expect(control.snapshot.feedback?.status).toBe('timeout');
  });

  it('ignores duplicate result, old result after newer request, wrong peer/action/target', async () => {
    const control = controller();
    deliverController(rawPresence('a'));
    deliverController(rawPresence('b'));
    const first = control.session.request('a', 'recenter');
    const reply = {
      v: 1,
      type: 'result',
      sender: 'a',
      target: control.session.id,
      seq: 101,
      requestId: first,
      action: 'recenter',
      status: 'accepted',
      fullscreen: false,
    };
    deliverController(reply);
    expect(control.snapshot.feedback?.status).toBe('accepted');
    deliverController({ ...reply, status: 'failed' });
    expect(control.snapshot.feedback?.status).toBe('accepted');
    const second = control.session.request('a', 'fullscreen');
    deliverController({ ...reply, seq: 102 });
    deliverController({
      ...reply,
      requestId: second,
      action: 'fullscreen',
      sender: 'b',
    });
    deliverController({ ...reply, requestId: second, seq: 103 });
    deliverController({
      ...reply,
      requestId: second,
      action: 'fullscreen',
      target: 'other',
      seq: 104,
    });
    expect(control.snapshot.feedback?.status).toBe('pending');
    deliverController({
      ...reply,
      requestId: second,
      action: 'fullscreen',
      fullscreen: true,
      seq: 105,
    });
    expect(control.snapshot.feedback?.status).toBe('accepted');
    expect(
      control.snapshot.peers.find((peer) => peer.id === 'a')?.fullscreen
    ).toBe(true);
  });

  it('does not send unsupported or unknown targets and host rechecks current capability', async () => {
    const control = controller();
    const host = display();
    await MemoryChannel.flush();
    host.peer.actions = ['recenter'];
    host.session.publishPresence();
    await MemoryChannel.flush();
    expect(control.session.request(host.session.id, 'fullscreen')).toBeNull();
    expect(control.session.request('missing', 'recenter')).toBeNull();
    expect(
      MemoryChannel.sent.filter((message) => message.type === 'command')
    ).toHaveLength(0);
    control.session.request(host.session.id, 'recenter');
    host.peer.actions = [];
    await MemoryChannel.flush();
    expect(control.snapshot.feedback?.status).toBe('unsupported');
    expect(host.onCommand).not.toHaveBeenCalled();
  });

  it('bounds duplicate memory at 128 sender/request pairs in FIFO order', async () => {
    const host = display();
    const channel = MemoryChannel.instances[0];
    const command = {
      v: 1,
      type: 'command',
      sender: 'controller',
      target: host.session.id,
      seq: 1,
      requestId: 'first',
      action: 'recenter',
      expiresAtMs: 3000,
    };
    channel.deliver(command);
    await MemoryChannel.flush();
    for (let i = 0; i < 127; i++)
      channel.deliver({ ...command, requestId: `request-${i}`, seq: i + 2 });
    await MemoryChannel.flush();
    channel.deliver(command);
    expect(host.onCommand).toHaveBeenCalledTimes(128);
    channel.deliver({ ...command, requestId: 'last', seq: 129 });
    await MemoryChannel.flush();
    channel.deliver(command);
    await MemoryChannel.flush();
    expect(host.onCommand).toHaveBeenCalledTimes(130);
    channel.deliver({ ...command, sender: 'another-controller', seq: 1 });
    await MemoryChannel.flush();
    expect(host.onCommand).toHaveBeenCalledTimes(131);
  });

  it.each(['reject', 'throw'])(
    'command callback %s yields failed rather than an unhandled error',
    async (mode) => {
      const control = controller();
      const host = display(
        vi.fn(() => {
          if (mode === 'throw') throw new Error('failed');
          return Promise.reject(new Error('failed'));
        })
      );
      await MemoryChannel.flush();
      control.session.request(host.session.id, 'recenter');
      await MemoryChannel.flush();
      expect(control.snapshot.feedback?.status).toBe('failed');
    }
  );

  it('ignores malformed, oversized, unknown and self-originated messages without side effects', async () => {
    const control = controller();
    const host = display();
    await MemoryChannel.flush();
    const channel = MemoryChannel.instances[1];
    const base = {
      v: 1,
      type: 'command',
      sender: 'control',
      target: host.session.id,
      seq: 1,
      requestId: 'request',
      action: 'recenter',
      expiresAtMs: 3000,
    };
    for (const message of [
      null,
      { ...base, v: 2 },
      { ...base, sender: 'x'.repeat(129) },
      { ...base, type: 'eval' },
      { ...base, payload: 'reload()' },
      { ...base, sender: host.session.id },
    ])
      channel.deliver(message);
    deliverController({ ...rawPresence('malformed'), actions: ['unknown'] });
    expect(host.onCommand).not.toHaveBeenCalled();
    expect(control.snapshot.peers.map((peer) => peer.id)).toEqual([
      host.session.id,
    ]);
  });

  it('closing during a command suppresses completion and later execution', async () => {
    let complete!: (result: DisplayResult) => void;
    const control = controller();
    const host = display(
      vi.fn(
        () =>
          new Promise<DisplayResult>((resolve) => {
            complete = resolve;
          })
      )
    );
    await MemoryChannel.flush();
    control.session.request(host.session.id, 'recenter');
    await MemoryChannel.flush();
    host.session.close();
    const sent = MemoryChannel.sent.length;
    complete('accepted');
    await MemoryChannel.flush();
    expect(MemoryChannel.sent).toHaveLength(sent);
    expect(control.snapshot.feedback?.status).toBe('unavailable');
  });
});

describe('transport availability', () => {
  it.each(['missing', 'constructor', 'post'])(
    '%s channel fails safely with no leaked resources',
    (mode) => {
      if (mode === 'missing') vi.stubGlobal('BroadcastChannel', undefined);
      if (mode === 'constructor') MemoryChannel.failConstructor = true;
      if (mode === 'post') MemoryChannel.failPost = true;
      const control = controller();
      expect(control.snapshot.available).toBe(false);
      expect(control.session.request('a', 'recenter')).toBeNull();
      expect(vi.getTimerCount()).toBe(0);
      expect(
        MemoryChannel.instances.every(
          (channel) =>
            channel.closed &&
            [...channel.listeners.values()].every((set) => set.size === 0)
        )
      ).toBe(true);
    }
  );

  it('post failure during a request clears peers and settles pending state as unavailable', async () => {
    const control = controller();
    display();
    await MemoryChannel.flush();
    MemoryChannel.failPost = true;
    expect(
      control.session.request(control.snapshot.peers[0].id, 'recenter')
    ).toBeNull();
    expect(control.snapshot).toMatchObject({
      available: false,
      peers: [],
      feedback: { status: 'unavailable' },
    });
    expect(MemoryChannel.instances[0].closed).toBe(true);
  });

  it('close stays silent and releases resources even if departure cannot be posted', () => {
    const control = controller();
    const count = control.updates.length;
    MemoryChannel.failPost = true;
    control.session.close();
    expect(control.updates).toHaveLength(count);
    expect(vi.getTimerCount()).toBe(0);
    expect(MemoryChannel.instances[0].closed).toBe(true);
  });

  it('creates unique UUID sessions and requests when secure-context randomUUID is unavailable', async () => {
    const getRandomValues = crypto.getRandomValues.bind(crypto);
    vi.stubGlobal('crypto', { getRandomValues });
    const control = controller();
    const host = display();
    await MemoryChannel.flush();
    expect(control.snapshot.available).toBe(true);
    expect(host.session.id).toMatch(
      /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i
    );
    expect(host.session.id).not.toBe(control.session.id);
    const requestId = control.session.request(host.session.id, 'recenter');
    expect(requestId).toMatch(
      /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i
    );
    await MemoryChannel.flush();
    expect(control.snapshot.feedback?.status).toBe('accepted');
  });

  it('messageerror disables the session and releases its scheduler', () => {
    const control = controller();
    const channel = MemoryChannel.instances[0];
    for (const listener of channel.listeners.get('messageerror') ?? [])
      listener(new Event('messageerror'));
    expect(control.snapshot.available).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    expect(channel.closed).toBe(true);
  });
});
