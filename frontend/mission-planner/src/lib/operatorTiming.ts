/** Local browser diagnostics only; no record content or network reporting. */
export function operatorTiming(stage: string, start: number) {
  try {
    performance.measure(`operator.save.${stage}`, {
      start,
      end: performance.now(),
    });
  } catch {
    // Instrumentation must never affect a journal operation.
  }
}
