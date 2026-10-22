const parts = new Map<number, string[]>();
(globalThis as any).__stage3Rows = [];
(globalThis as any).__perf391Host = {
  run: "synthetic-test",
  page: "p",
  document: "d1",
};
(globalThis as any).__perf391Binding = async (m: any) => {
  const p = parts.get(m.seq) ?? [];
  p[m.part] = m.payload;
  parts.set(m.seq, p);
  if (p.filter((x) => x !== undefined).length === m.total) {
    (globalThis as any).__stage3Rows.push(JSON.parse(p.join("")));
    parts.delete(m.seq);
  }
  return true;
};
