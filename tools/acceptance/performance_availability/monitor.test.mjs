import assert from "node:assert/strict";
import { test } from "node:test";
import { serialReader } from "./serial.mjs";
test("a delayed state response cannot reverse simultaneous capture streams", async () => {
  let release;
  const first = new Promise((r) => {
    release = r;
  });
  const started = [],
    completed = [];
  const read = serialReader(async (name) => {
    started.push(name);
    if (name === "periodic") await first;
    completed.push(name);
    return name;
  });
  const a = read("periodic"),
    b = read("transition");
  await Promise.resolve();
  assert.deepEqual(started, ["periodic"]);
  release();
  assert.deepEqual(await Promise.all([a, b]), ["periodic", "transition"]);
  assert.deepEqual(completed, ["periodic", "transition"]);
});
