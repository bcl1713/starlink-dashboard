/** Validator for the schema keywords used by the shared, closed v1 contract. */
import { readFileSync } from "node:fs";
const schema = JSON.parse(
  readFileSync(
    new URL("./perf391_network_evidence/event-schema.json", import.meta.url),
    "utf8",
  ),
);

function check(value, rule) {
  if (rule === true) return;
  if (rule === false) throw Error("additional property");
  if ("const" in rule && value !== rule.const) throw Error("const mismatch");
  if (rule.enum && !rule.enum.includes(value)) throw Error("enum mismatch");
  if (rule.type) {
    const types = Array.isArray(rule.type) ? rule.type : [rule.type];
    const valid = types.some((t) =>
      t === "null"
        ? value === null
        : t === "array"
          ? Array.isArray(value)
          : t === "object"
            ? value !== null &&
              typeof value === "object" &&
              !Array.isArray(value)
            : t === "integer"
              ? Number.isSafeInteger(value)
              : t === "number"
                ? typeof value === "number" && Number.isFinite(value)
                : typeof value === t,
    );
    if (!valid) throw Error("type mismatch");
  }
  if (
    typeof value === "number" &&
    rule.minimum !== undefined &&
    value < rule.minimum
  )
    throw Error("minimum");
  if (
    typeof value === "string" &&
    ((rule.minLength && value.length < rule.minLength) ||
      (rule.pattern && !new RegExp(rule.pattern).test(value)))
  )
    throw Error("string constraint");
  if (
    rule.anyOf &&
    !rule.anyOf.some((r) => {
      try {
        check(value, r);
        return true;
      } catch {
        return false;
      }
    })
  )
    throw Error("anyOf mismatch");
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    for (const key of rule.required ?? [])
      if (!(key in value)) throw Error(`missing ${key}`);
    for (const [key, v] of Object.entries(value)) {
      if (rule.properties && key in rule.properties)
        check(v, rule.properties[key]);
      else if ("additionalProperties" in rule)
        check(v, rule.additionalProperties);
    }
  }
  if (Array.isArray(value)) {
    if (
      (rule.minItems !== undefined && value.length < rule.minItems) ||
      (rule.maxItems !== undefined && value.length > rule.maxItems)
    )
      throw Error("array size");
    if (rule.items) for (const item of value) check(item, rule.items);
  }
  if (rule.allOf) for (const r of rule.allOf) check(value, r);
  if (rule.if) {
    let matches = true;
    try {
      check(value, rule.if);
    } catch {
      matches = false;
    }
    if (matches && rule.then) check(value, rule.then);
  }
}

export function validateEvent(row) {
  // Also reject nonfinite values in open identity metadata before stringify.
  JSON.stringify(row, (_, value) => {
    if (typeof value === "number" && !Number.isFinite(value))
      throw Error("nonfinite number");
    return value;
  });
  check(row, schema);
  const d = row.data;
  if (row.kind === "scrape" && (d.state === "finite") !== (d.value !== null))
    throw Error("scrape state/value mismatch");
  if (["chart", "evaluation"].includes(row.kind)) {
    if (d.times.some((t, i) => i && t <= d.times[i - 1]))
      throw Error("timestamps must increase");
    const arrays =
      row.kind === "chart"
        ? Object.values(d.traces)
        : [d.values, d.sample_timestamps];
    if (arrays.some((a) => a.length !== d.times.length))
      throw Error("array lengths");
    if (row.kind === "chart") {
      if (d.viewport.length !== 2 || d.viewport[1] <= d.viewport[0])
        throw Error("viewport");
      if (
        d.visible_gaps?.some(
          (v, i) =>
            v.length !== 2 ||
            v[1] <= v[0] ||
            (i && d.visible_gaps[i - 1][1] > v[0]),
        )
      )
        throw Error("gap intervals");
    }
  }
  return row;
}
