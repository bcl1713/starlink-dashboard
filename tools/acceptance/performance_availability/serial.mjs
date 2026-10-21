/** Serialize owned observer reads; completion order cannot invert capture order. */
export function serialReader(read) {
  let tail = Promise.resolve();
  return (...args) => {
    const next = tail.then(() => read(...args));
    tail = next.catch(() => {});
    return next;
  };
}
