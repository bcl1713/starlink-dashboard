/** A request owns exactly one Chromium process, its contexts and asset listener. */
import { chromium } from 'playwright-core';
import { createServer } from 'node:http';
import {
  readFile,
  writeFile,
  mkdir,
  readdir,
  realpath,
  rm,
} from 'node:fs/promises';
import { once } from 'node:events';
import path from 'node:path';
import { within } from './render-budget.mjs';

export function ownedPath(root, name) {
  const result = path.resolve(root, name);
  if (
    result !== path.resolve(root) &&
    !result.startsWith(path.resolve(root) + path.sep)
  )
    throw Object.assign(new Error('Invalid owned path'), { code: 'resource' });
  return result;
}
async function processInfo(pid) {
  try {
    const parts = (await readFile(`/proc/${pid}/stat`, 'utf8'))
      .split(') ')[1]
      .split(' ');
    return {
      pid: Number(pid),
      state: parts[0],
      ppid: Number(parts[1]),
      pgid: Number(parts[2]),
      start: parts[19],
    };
  } catch {
    return null;
  }
}
async function descendants(pid) {
  const infos = await Promise.all(
    (await readdir('/proc')).filter((n) => /^\d+$/.test(n)).map(processInfo)
  );
  const tree = [];
  const parents = new Set([pid]);
  let more = true;
  while (more) {
    more = false;
    for (const info of infos) {
      if (info && parents.has(info.ppid) && !parents.has(info.pid)) {
        parents.add(info.pid);
        tree.push(info);
        more = true;
      }
    }
  }
  return tree;
}
async function alive(info) {
  const current = await processInfo(info.pid);
  return !!current && current.start === info.start && current.state !== 'Z';
}
export async function openRenderOwner({
  assetRoot,
  outputRoot,
  ownershipPath,
  budget,
  fault,
}) {
  assetRoot = await realpath(assetRoot);
  ownershipPath = ownedPath(outputRoot, ownershipPath);
  const temp = ownedPath(outputRoot, 'browser-temp');
  await mkdir(temp, { recursive: true });
  const self = await processInfo(process.pid);
  const ownership = {
    pid: process.pid,
    pgid: self.pgid,
    start: self.start,
    browserPid: null,
    browserPgid: null,
    browserStart: null,
    listener: null,
    contexts: [],
    workers: [],
    temporaryPaths: [temp],
    command: process.argv.slice(0, 2),
  };
  const contexts = new Set(),
    sockets = new Set(),
    workers = new Set();
  let server, browserServer, browser, closing;
  const persist = () =>
    writeFile(ownershipPath, JSON.stringify(ownership, null, 2));
  await persist();
  const owner = {
    budget,
    outputRoot,
    browser: null,
    origin: null,
    ownership,
    async trackChild(child, command) {
      workers.add(child);
      const record = {
        pid: child.pid,
        pgid: child.pid,
        start: (await processInfo(child.pid))?.start ?? null,
        command,
        reaped: false,
      };
      ownership.workers.push(record);
      await persist();
      if (closing) child.kill('SIGTERM');
      return async () => {
        record.reaped = child.exitCode !== null || child.signalCode !== null;
        record.exitCode = child.exitCode;
        record.signalCode = child.signalCode;
        if (record.reaped) workers.delete(child);
        await persist();
      };
    },
    async newContext(options, { remainingMs = budget.workRemainingMs } = {}) {
      remainingMs();
      let abandoned = false;
      let acquisition = browser.newContext(options);
      if (fault === 'map-context-late' && options.viewport.width === 1920) {
        const delay = budget.mapRemainingMs() + 50;
        acquisition = acquisition.then(
          (context) =>
            new Promise((resolve) => {
              setTimeout(() => resolve(context), delay);
            })
        );
      }
      const pending = acquisition.then((context) => {
        contexts.add(context);
        ownership.contexts.push(ownership.contexts.length + 1);
        context.once('close', () => contexts.delete(context));
        if (abandoned || closing) void context.close().catch(() => {});
        return context;
      });
      try {
        const context = await within(pending, remainingMs());
        await persist();
        return context;
      } catch (error) {
        abandoned = true;
        throw error;
      }
    },
    close() {
      if (closing) return closing;
      closing = (async () => {
        const errors = [];
        const workerOwned = [];
        for (const child of workers) {
          workerOwned.push(...(await descendants(child.pid)));
          if (child.exitCode === null && child.signalCode === null) {
            try {
              process.kill(-child.pid, 'SIGTERM');
            } catch {}
            try {
              await within(
                once(child, 'close'),
                Math.max(1, Math.min(250, budget.remainingMs()))
              );
            } catch {
              try {
                process.kill(-child.pid, 'SIGKILL');
              } catch {}
              await within(once(child, 'close'), 1000).catch((e) =>
                errors.push(String(e))
              );
            }
          }
        }
        const owned = browserServer
          ? await descendants(browserServer.process().pid)
          : [];
        owned.push(...workerOwned);
        let contextsClosed = true;
        for (const context of [...contexts]) {
          try {
            await within(context.close(), Math.max(1, budget.remainingMs()));
          } catch {
            contextsClosed = false;
          }
        }
        if (browserServer) {
          try {
            await within(
              browserServer.close(),
              Math.max(1, budget.remainingMs())
            );
          } catch {
            await browserServer.kill().catch((e) => errors.push(String(e)));
          }
        }
        for (const info of owned) {
          if (await alive(info)) {
            try {
              process.kill(info.pid, 'SIGTERM');
            } catch {}
          }
        }
        for (const info of owned) {
          if (await alive(info)) {
            try {
              process.kill(info.pid, 'SIGKILL');
            } catch {}
          }
        }
        const child = browserServer?.process();
        if (child && child.exitCode === null && child.signalCode === null) {
          await within(once(child, 'exit'), 1000).catch((e) =>
            errors.push(String(e))
          );
        }
        let listenerClosed = true;
        if (server) {
          for (const socket of sockets) socket.destroy();
          await new Promise((resolve) =>
            server.close((e) => {
              if (e) {
                listenerClosed = false;
                errors.push(String(e));
              }
              resolve();
            })
          );
        }
        await rm(temp, { recursive: true, force: true });
        const survivors = [];
        for (const info of owned) {
          if (await alive(info)) survivors.push(info.pid);
        }
        const browserExited =
          !child || child.exitCode !== null || child.signalCode !== null;
        if (browserExited) contexts.clear();
        const cleanup = {
          contextsClosed:
            (contextsClosed && contexts.size === 0) || browserExited,
          browserExited:
            !child || child.exitCode !== null || child.signalCode !== null,
          listenerClosed,
          survivors,
          errors,
          contextCount: ownership.contexts.length,
          childrenReaped:
            (!child || child.exitCode !== null || child.signalCode !== null) &&
            [...workers].every(
              (c) => c.exitCode !== null || c.signalCode !== null
            ),
        };
        cleanup.success =
          cleanup.contextsClosed &&
          cleanup.browserExited &&
          listenerClosed &&
          cleanup.childrenReaped &&
          !survivors.length &&
          !errors.length;
        ownership.cleanup = cleanup;
        await persist();
        return cleanup;
      })();
      return closing;
    },
  };
  try {
    server = createServer(async (request, response) => {
      try {
        const raw = decodeURIComponent(request.url.split('?')[0]);
        if (raw.includes('..') || raw.includes('\\'))
          throw new Error('Traversal');
        const file = await realpath(ownedPath(assetRoot, '.' + raw));
        ownedPath(assetRoot, file);
        const mime = {
          '.html': 'text/html',
          '.js': 'text/javascript',
          '.jpg': 'image/jpeg',
          '.png': 'image/png',
        };
        response.setHeader(
          'Content-Type',
          mime[path.extname(file)] || 'application/octet-stream'
        );
        response.setHeader('Cache-Control', 'no-store');
        response.end(await readFile(file));
      } catch {
        response.writeHead(404);
        response.end('Local asset unavailable');
      }
    });
    server.on('connection', (socket) => {
      sockets.add(socket);
      socket.once('close', () => sockets.delete(socket));
    });
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    ownership.listener = { address: '127.0.0.1', port: server.address().port };
    owner.origin = `http://127.0.0.1:${server.address().port}`;
    await persist();
    if (fault === 'startup')
      throw Object.assign(new Error('Injected launch rejection'), {
        code: 'startup',
      });
    browserServer = await chromium.launchServer({
      headless: true,
      host: '127.0.0.1',
      env: { ...process.env, TMPDIR: temp },
      timeout: budget.workRemainingMs(),
      args: [
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--disable-dev-shm-usage',
      ],
    });
    const child = browserServer.process();
    ownership.browserPid = child.pid;
    const browserProcess = await processInfo(child.pid);
    ownership.browserPgid = browserProcess.pgid;
    ownership.browserStart = browserProcess.start;
    await persist();
    browser = await chromium.connect(browserServer.wsEndpoint(), {
      timeout: budget.workRemainingMs(),
    });
    owner.browser = browser;
    owner.browserIdentity = {
      version: browser.version(),
      executable: await realpath(`/proc/${child.pid}/exe`),
    };
    return owner;
  } catch (error) {
    error.cleanup = await owner.close();
    throw error;
  }
}
