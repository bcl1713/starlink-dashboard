/** Diagnostic counters only: never retain history, DOM nodes or uptime arrays. */
export function installOverviewHistoryProbe() {
  const state = {
    historyParseCount: 0,
    historyParseMs: 0,
    historyParseMaxMs: 0,
    plotClears: 0,
    longTasks: 0,
    longTaskMs: 0,
    longTaskMaxMs: 0,
    frames: 0,
    frameMs: 0,
    frameMaxMs: 0,
  };
  const parse = JSON.parse;
  JSON.parse = function (...args) {
    const began = performance.now();
    const value = parse.apply(this, args);
    if (
      value &&
      typeof value === "object" &&
      value.series &&
      value.rolling_5m &&
      Number.isFinite(value.window_seconds)
    ) {
      const elapsed = performance.now() - began;
      state.historyParseCount++;
      state.historyParseMs += elapsed;
      state.historyParseMaxMs = Math.max(state.historyParseMaxMs, elapsed);
    }
    return value;
  };
  const clear = CanvasRenderingContext2D.prototype.clearRect;
  CanvasRenderingContext2D.prototype.clearRect = function (...args) {
    if (this.canvas.closest?.(".uplot")) state.plotClears++;
    return clear.apply(this, args);
  };
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      state.longTasks++;
      state.longTaskMs += entry.duration;
      state.longTaskMaxMs = Math.max(state.longTaskMaxMs, entry.duration);
    }
  });
  observer.observe({ type: "longtask", buffered: true });
  let last;
  function frame(now) {
    if (document.hidden) last = undefined;
    else {
      if (last !== undefined) {
        const elapsed = now - last;
        state.frames++;
        state.frameMs += elapsed;
        state.frameMaxMs = Math.max(state.frameMaxMs, elapsed);
      }
      last = now;
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  window.__overviewHistoryProbe = { snapshot: () => ({ ...state }) };
}
