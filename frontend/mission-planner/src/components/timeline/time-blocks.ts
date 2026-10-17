/** Collapse adjacent display-equivalent intervals without changing source data. */
export function timeBlocks<T>(
  rows: readonly T[],
  start: (row: T) => string,
  end: (row: T) => string,
  key: (row: T) => string,
  extend: (row: T, end: string) => T
): T[] {
  const blocks: T[] = [];
  for (const row of rows) {
    const previous = blocks.at(-1);
    if (
      previous &&
      Number.isFinite(Date.parse(start(row))) &&
      Date.parse(end(previous)) === Date.parse(start(row)) &&
      key(previous) === key(row)
    ) {
      blocks[blocks.length - 1] = extend(previous, end(row));
    } else {
      blocks.push(row);
    }
  }
  return blocks;
}
