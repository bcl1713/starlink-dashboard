const exited = (child) => child.exitCode !== null || child.signalCode !== null;
function waitForExit(child, milliseconds) {
  if (exited(child)) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      child.removeListener('exit', done);
      resolve();
    };
    const timer = setTimeout(done, milliseconds);
    child.once('exit', done);
  });
}

// Only accepts the runner's live ChildProcess handle, spawned as its own group.
export async function stopExperimentServer(child, graceMs = 3000) {
  if (!child || exited(child)) return;
  child.kill('SIGTERM');
  await waitForExit(child, graceMs);
  if (exited(child)) return;
  process.kill(-child.pid, 'SIGKILL');
  await waitForExit(child, graceMs);
  if (!exited(child)) throw new Error(`Owned server ${child.pid} did not exit`);
}

export async function downloadAfterClick(waitForDownload, click) {
  // Attach handlers to both promises immediately: closing the browser while a
  // click is pending must not cause an unhandled download rejection.
  const [download] = await Promise.all([
    waitForDownload(),
    Promise.resolve().then(click),
  ]);
  return download;
}
