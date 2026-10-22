/** Check only the synthetic diagnostic workload, never acceptance limits. */
export function validateWorkload(
  traffic,
  errors,
  viewers,
  operator,
  start,
  end,
) {
  if (errors.length)
    throw new Error("Browser errors invalidate diagnostic workload");
  const results = [];
  for (let page = 0; page < viewers + Number(operator); page++) {
    const paths =
      page < viewers
        ? ["/api/status", "/api/overview-history"]
        : ["/api/v2/operator/health"];
    const counts = Object.fromEntries(
      paths.map((path) => [
        path,
        traffic.filter(
          (r) =>
            r.page === page &&
            r.path === path &&
            r.ns >= start &&
            r.ns <= end &&
            r.status === 200,
        ).length,
      ]),
    );
    if (Object.values(counts).some((count) => count < 2))
      throw new Error("Missing recurring measured traffic on page " + page);
    results.push({ page, counts });
  }
  return results;
}

export function wireRequestId(headers) {
  return typeof headers === "string"
    ? (/x-diagnostic-id: (diag-[0-9]{1,30})\r?\n/i.exec(headers)?.[1] ?? null)
    : null;
}
