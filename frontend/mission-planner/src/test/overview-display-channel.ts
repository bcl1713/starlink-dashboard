import type { OverviewDisplayMessage } from '../services/overview-display-protocol';

// Separate endpoints, ordered asynchronous delivery, and no self-delivery.
export class OverviewTestChannel {
  static instances: OverviewTestChannel[] = [];
  static sent: OverviewDisplayMessage[] = [];
  static queue: (() => void)[] = [];
  static failPost = false;
  listeners = new Map<string, Set<EventListener>>();
  closed = false;
  addEventListener(type: string, listener: EventListener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: EventListener) {
    this.listeners.get(type)?.delete(listener);
  }
  constructor() {
    OverviewTestChannel.instances.push(this);
  }
  postMessage(message: OverviewDisplayMessage) {
    if (OverviewTestChannel.failPost) throw new Error('channel failed');
    OverviewTestChannel.sent.push(structuredClone(message));
    for (const peer of OverviewTestChannel.instances) {
      if (peer === this || peer.closed) continue;
      OverviewTestChannel.queue.push(() => {
        if (!peer.closed) peer.deliver(message);
      });
    }
  }
  deliver(message: OverviewDisplayMessage) {
    for (const listener of this.listeners.get('message') ?? [])
      listener(new MessageEvent('message', { data: structuredClone(message) }));
  }
  close() {
    this.closed = true;
  }
  static reset() {
    this.instances = [];
    this.sent = [];
    this.queue = [];
    this.failPost = false;
  }
  static async flush() {
    for (let i = 0; i < 12; i++) {
      while (OverviewTestChannel.queue.length)
        OverviewTestChannel.queue.shift()!();
      await Promise.resolve();
    }
  }
}
