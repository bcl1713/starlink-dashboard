import { vi } from 'vitest';

export const createdPlots: MockUPlot[] = [];

export class MockUPlot {
  readonly root = document.createElement('div');
  readonly setData = vi.fn();
  readonly setSize = vi.fn();
  readonly destroy = vi.fn();
  readonly options: unknown;
  readonly data: unknown;
  readonly target: HTMLElement;

  constructor(options: unknown, data: unknown, target: HTMLElement) {
    this.options = options;
    this.data = data;
    this.target = target;
    this.root.className = 'uplot';
    this.root.append(document.createElement('canvas'));
    target.append(this.root);
    createdPlots.push(this);
  }
}

export function resetUPlotMock(): void {
  createdPlots.length = 0;
}
