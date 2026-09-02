export type Cadence = 1 | 2 | 5 | 10 | 30 | 'paused';

export class CompletionPoller {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private active: Promise<void> | undefined;
  private cadence: Cadence;
  private running = false;
  private visible = true;
  private readonly request: () => Promise<void>;

  constructor(request: () => Promise<void>, cadence: Cadence = 1) {
    this.request = request;
    this.cadence = cadence;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.schedule();
  }

  stop(): void {
    this.running = false;
    this.clearTimer();
  }

  setCadence(cadence: Cadence): void {
    this.cadence = cadence;
    if (!this.active) this.schedule();
  }

  setVisible(visible: boolean): void {
    if (this.visible === visible) return;
    this.visible = visible;
    this.clearTimer();
    if (visible && this.running) void this.run().catch(() => {});
  }

  manual(): Promise<void> {
    if (this.active) return this.active;
    return this.run();
  }

  private schedule(): void {
    this.clearTimer();
    if (!this.running || !this.visible || this.cadence === 'paused') return;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      void this.run().catch(() => {});
    }, this.cadence * 1000);
  }

  private run(): Promise<void> {
    if (!this.running || !this.visible) return Promise.resolve();
    if (this.active) return this.active;
    this.clearTimer();
    const operation = Promise.resolve()
      .then(this.request)
      .finally(() => {
        if (this.active === operation) this.active = undefined;
        this.schedule();
      });
    this.active = operation;
    return operation;
  }

  private clearTimer(): void {
    if (this.timer !== undefined) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
  }
}
