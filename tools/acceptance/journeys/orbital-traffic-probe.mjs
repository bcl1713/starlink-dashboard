/** Browser-owned instrumentation. No changes to product rendering or worker messages. */
export function installOrbitalProbe() {
  const p = (window.__orbitalProbe = {
    workers: new Set(),
    created: 0,
    terminated: 0,
    snapshots: [],
    errors: [],
    buffers: new Map(),
    draws: 0,
    spriteDraws: 0,
    spriteFrames: [],
    drawFrames: [],
    frames: [],
    longTasks: [],
    uploads: [],
    handlers: [],
    reset() {
      this.frames = [];
      this.drawFrames = [];
      this.spriteFrames = [];
      this.longTasks = [];
      this.uploads = [];
      this.handlers = [];
      this.snapshots = [];
    },
    read() {
      return {
        activeWorkers: this.workers.size,
        created: this.created,
        terminated: this.terminated,
        buffers: this.buffers.size,
        bufferBytes: [...this.buffers.values()].reduce((a, b) => a + b, 0),
        bufferContexts: new Set(owners.values()).size,
        orbitalBufferBytes: [...this.buffers.values()]
          .filter((n) => n === 196608 || n === 65536)
          .reduce((a, b) => a + b, 0),
        maximumSpriteDrawsPerFrame: Math.max(0, ...this.spriteFrames),
        snapshots: this.snapshots,
        frames: this.frames,
        drawFrames: this.drawFrames,
        longTasks: this.longTasks,
        uploads: this.uploads,
        handlers: this.handlers,
        errors: this.errors,
      };
    },
    failWorker() {
      for (const w of this.workers)
        w.dispatchEvent(
          new ErrorEvent("error", { message: "Controlled acceptance failure" }),
        );
    },
  });
  const BaseWorker = window.Worker;
  window.Worker = class extends BaseWorker {
    constructor(...args) {
      super(...args);
      p.workers.add(this);
      p.created++;
      super.addEventListener("message", (event) => {
        const s = event.data;
        if (s.type === "snapshot")
          p.snapshots.push({
            updateMs: s.snapshot.updateMs,
            size: s.snapshot.ids.length,
            valid: s.snapshot.valid.reduce((n, v) => n + Boolean(v), 0),
            route: s.snapshot.route?.ids ?? null,
            utcMs: s.snapshot.utcMs,
          });
      });
      super.addEventListener("error", (event) => p.errors.push(event.message));
    }
    set onmessage(fn) {
      super.onmessage =
        typeof fn === "function"
          ? (event) => {
              const started = performance.now();
              try {
                fn.call(this, event);
              } finally {
                p.handlers.push(performance.now() - started);
              }
            }
          : fn;
    }
    get onmessage() {
      return super.onmessage;
    }
    addEventListener(type, fn, ...args) {
      if (type !== "message" || typeof fn !== "function")
        return super.addEventListener(type, fn, ...args);
      return super.addEventListener(
        type,
        (...a) => {
          const start = performance.now();
          fn.apply(this, a);
          p.handlers.push(performance.now() - start);
        },
        ...args,
      );
    }
    terminate() {
      if (p.workers.delete(this)) p.terminated++;
      super.terminate();
    }
  };
  const bound = new Map();
  const owners = new Map();
  const watched = new WeakSet();
  for (const prototype of [
    WebGLRenderingContext.prototype,
    WebGL2RenderingContext.prototype,
  ]) {
    for (const name of [
      "createBuffer",
      "deleteBuffer",
      "bindBuffer",
      "bufferData",
      "drawArrays",
      "drawElements",
      "drawArraysInstanced",
      "drawElementsInstanced",
    ]) {
      if (!prototype[name]) continue;
      const original = prototype[name];
      prototype[name] = function (...args) {
        const start = performance.now();
        const result = original.apply(this, args);
        if (name === "createBuffer") {
          p.buffers.set(result, 0);
          owners.set(result, this);
          if (!watched.has(this)) {
            watched.add(this);
            const context = this;
            this.canvas.addEventListener("webglcontextlost", () => {
              for (const [buffer, owner] of owners)
                if (owner === context) {
                  p.buffers.delete(buffer);
                  owners.delete(buffer);
                }
            });
          }
        }
        if (name === "deleteBuffer") {
          p.buffers.delete(args[0]);
          owners.delete(args[0]);
        }
        if (name === "bindBuffer") bound.set(args[0], args[1]);
        if (name === "bufferData") {
          const size =
            typeof args[1] === "number" ? args[1] : (args[1]?.byteLength ?? 0);
          const buffer = bound.get(args[0]);
          if (p.buffers.has(buffer)) p.buffers.set(buffer, size);
          if (size === 196608 || size === 65536)
            p.uploads.push(performance.now() - start);
        }
        if (name.startsWith("draw")) {
          p.draws++;
          if (
            name.startsWith("drawArrays") &&
            args[0] === this.POINTS &&
            [2048, 16384].includes(args[2])
          )
            p.spriteDraws++;
        }
        return result;
      };
    }
  }
  let last = performance.now();
  function frame(now) {
    if (p.frames.length < 100000) p.frames.push(now - last);
    last = now;
    p.drawFrames.push(p.draws);
    p.spriteFrames.push(p.spriteDraws);
    p.spriteDraws = 0;
    p.draws = 0;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  new PerformanceObserver((list) => {
    for (const e of list.getEntries())
      p.longTasks.push({ start: e.startTime, duration: e.duration });
  }).observe({ type: "longtask", buffered: true });
}
export function summarizeProbe(raw, seconds) {
  const percentile = (values, fraction) => {
    const sorted = values.slice().sort((a, b) => a - b);
    return (
      sorted[
        Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))
      ] ?? null
    );
  };
  return {
    activeWorkers: raw.activeWorkers,
    created: raw.created,
    terminated: raw.terminated,
    buffers: raw.buffers,
    bufferBytes: raw.bufferBytes,
    orbitalBufferBytes: raw.orbitalBufferBytes,
    maximumSpriteDrawsPerFrame: raw.maximumSpriteDrawsPerFrame,
    fps: raw.frames.length / seconds,
    p95FrameMs: percentile(raw.frames, 0.95),
    maximumDrawsPerFrame: Math.max(0, ...raw.drawFrames),
    workerUpdates: raw.snapshots.length,
    workerP95Ms: percentile(
      raw.snapshots.map((s) => s.updateMs),
      0.95,
    ),
    workerMaxMs: Math.max(0, ...raw.snapshots.map((s) => s.updateMs)),
    snapshot: raw.snapshots.at(-1) ?? null,
    wholePageLongTasks: raw.longTasks.length,
    longestWholePageTaskMs: Math.max(
      0,
      ...raw.longTasks.map((e) => e.duration),
    ),
    maxInstrumentedSnapshotHandlerMs: Math.max(0, ...raw.handlers),
    maxInstrumentedOrbitalSizedUploadMs: Math.max(0, ...raw.uploads),
    errors: raw.errors,
  };
}
