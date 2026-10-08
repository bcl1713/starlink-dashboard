/** Map canonical display cells to measured PDF positions without reading PDF text. */
export function buildPdfExpectations(payload, measured) {
  if (
    JSON.stringify(measured.rows.map((r) => r.id)) !==
    JSON.stringify(payload.rows.map((r) => r.id))
  )
    throw new Error('PDF measured row assignment mismatch');
  const pt = (box) => box.map((v) => v * 0.75);
  return {
    schemaVersion: 1,
    pageCount: 1,
    pageSizePt: [960, 540],
    pages: [
      {
        page: 1,
        tableBodyBoundsPt: measured.tableBodyBoundsPx
          ? pt(measured.tableBodyBoundsPx)
          : null,
      },
    ],
    rows: payload.rows.map((r, i) => {
      if (
        r.displayCells?.length !== 4 ||
        measured.rows[i].cellBoundsPx?.length !== 4
      )
        throw new Error('PDF row requires four canonical cells and bounds');
      return {
        legId: payload.legId,
        rowId: r.id,
        page: 1,
        displayCells: r.displayCells,
        cellBoundsPt: measured.rows[i].cellBoundsPx.map(pt),
      };
    }),
  };
}
