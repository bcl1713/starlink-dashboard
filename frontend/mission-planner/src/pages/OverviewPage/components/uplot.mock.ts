import { vi } from 'vitest';
import type uPlot from 'uplot';

export const createdPlots: MockUPlot[] = [];
export const uplotMockFlags = {
  throwConstructor: false,
};

export class MockUPlot {
  readonly root = document.createElement('div');
  readonly setData = vi.fn();
  readonly setSize = vi.fn();
  readonly destroy = vi.fn();
  readonly options: uPlot.Options;
  readonly data: unknown;
  readonly target: HTMLElement;

  constructor(options: unknown, data: unknown, target?: HTMLElement) {
    if (uplotMockFlags.throwConstructor) throw new Error('constructor failed');
    this.options = options as uPlot.Options;
    this.data = data;
    this.target = target ?? document.createElement('div');
    this.root.className = 'uplot';
    this.root.append(document.createElement('canvas'));
    target?.append(this.root);
    createdPlots.push(this);
  }
}

export class MockResizeObserver {
  static callbacks: ResizeObserverCallback[] = [];
  static instances: MockResizeObserver[] = [];
  static throwConstructor = false;
  static throwObserve = false;

  observe = vi.fn(() => {
    if (MockResizeObserver.throwObserve) throw new Error('observe failed');
  });
  disconnect = vi.fn();
  readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    if (MockResizeObserver.throwConstructor) throw new Error('observer failed');
    this.callback = callback;
    MockResizeObserver.callbacks.push(callback);
    MockResizeObserver.instances.push(this);
  }
}

export function resetUPlotMock(): void {
  createdPlots.length = 0;
  uplotMockFlags.throwConstructor = false;
  MockResizeObserver.callbacks = [];
  MockResizeObserver.instances = [];
  MockResizeObserver.throwConstructor = false;
  MockResizeObserver.throwObserve = false;
}
