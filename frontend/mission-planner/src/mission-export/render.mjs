/** Request-owned static renderer. No persistent cache or mission storage writes. */
import { chromium } from 'playwright-core';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, readdir, rm } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const hash = (value) => createHash('sha256').update(value).digest('hex');
const mime = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
};
export async function renderStage({
  legs,
  output,
  assetRoot,
  budgetSeconds = 60,
  fault,
  ownershipPath = path.join(output, 'ownership.json'),
}) {
  const started = performance.now();
  const deadline = started + budgetSeconds * 1000;
  const remaining = () => {
    if (error === 'Renderer terminated') throw new Error(error);
    const ms = deadline - performance.now();
    if (ms <= 0) throw new Error('Shared renderer deadline exceeded');
    return Math.max(1, Math.floor(ms));
  };
  const ownership = {
    pid: process.pid,
    pgid: Number(
      (await readFile('/proc/self/stat', 'utf8')).split(') ')[1].split(' ')[2]
    ),
    browserPid: null,
    listener: null,
    contexts: 0,
    temporaryPaths: [output, path.join(output, 'browser-temp')],
    browserCommand: [
      'packaged-chromium-headless-shell',
      '--use-angle=swiftshader',
    ],
    compose: null,
    volumes: [],
  };
  await mkdir(output, { recursive: true });
  await mkdir(path.join(output, 'browser-temp'), { recursive: true });
  const recordOwnership = () =>
    writeFile(ownershipPath, JSON.stringify(ownership, null, 2));
  await recordOwnership();
  const views = [];
  const plannedViewIds = [];
  const readinessLog = [];
  let server, browserServer, browser, context;
  let error;
  let startupSeconds;
  const cleanup = {
    listenerClosed: false,
    browserExited: false,
    contextsClosed: false,
    errors: [],
  };
  const stop = () => {
    error = 'Renderer terminated';
    void context?.close().catch(() => {});
    void browserServer?.kill().catch(() => {});
  };
  // Reserve one second for cleanup within this request's shared budget.
  const watchdog = setTimeout(
    () => {
      error = 'Shared renderer deadline exceeded';
      void context?.close().catch(() => {});
      void browserServer?.kill().catch(() => {});
    },
    Math.max(1, budgetSeconds * 1000 - 1000)
  );
  process.once('SIGTERM', stop);
  process.once('SIGINT', stop);
  if (process.env.MISSION_MAP_PARENT_PIPE === '1') {
    process.stdin.once('end', stop);
    process.stdin.resume();
  }
  try {
    server = createServer(async (request, response) => {
      try {
        const pathname = decodeURIComponent(
          new URL(request.url, 'http://127.0.0.1').pathname
        );
        const file = path.resolve(assetRoot, `.${pathname}`);
        if (!file.startsWith(`${path.resolve(assetRoot)}${path.sep}`))
          throw new Error('Invalid asset path');
        response.setHeader(
          'Content-Type',
          mime[path.extname(file)] ?? 'application/octet-stream'
        );
        response.setHeader('Cache-Control', 'no-store');
        response.end(await readFile(file));
      } catch {
        response.writeHead(404);
        response.end('Local map asset unavailable');
      }
    });
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    const port = server.address().port;
    ownership.listener = { address: '127.0.0.1', port };
    await recordOwnership();
    browserServer = await chromium.launchServer({
      headless: true,
      host: '127.0.0.1',
      env: { ...process.env, TMPDIR: path.join(output, 'browser-temp') },
      timeout: remaining(),
      executablePath:
        fault === 'startup' ? '/nonexistent/mission-map-chromium' : undefined,
      args: [
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--disable-dev-shm-usage',
      ],
    });
    const browserProcess = browserServer.process();
    ownership.browserPid = browserProcess.pid;
    ownership.browserPgid = Number(
      (await readFile(`/proc/${browserProcess.pid}/stat`, 'utf8'))
        .split(') ')[1]
        .split(' ')[2]
    );
    await recordOwnership();
    browser = await chromium.connect(browserServer.wsEndpoint(), {
      timeout: remaining(),
    });
    startupSeconds = (performance.now() - started) / 1000;
    for (let legIndex = 0; legIndex < legs.length; legIndex++) {
      remaining();
      const input = legs[legIndex];
      const digest = hash(JSON.stringify(input));
      context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
        locale: 'en-US',
        timezoneId: 'UTC',
        reducedMotion: 'reduce',
      });
      ownership.contexts++;
      await recordOwnership();
      await context.route('**/*', async (route) => {
        const url = new URL(route.request().url());
        if (url.hostname !== '127.0.0.1' || url.port !== String(port))
          return route.abort('blockedbyclient');
        if (url.pathname === '/city-lights-mask.png' && fault === 'texture')
          return route.abort('failed');
        if (url.pathname === '/city-lights-mask.png' && fault === 'slow')
          return; // deadline, not readiness sleep
        return route.continue();
      });
      const page = await context.newPage();
      page.on('console', (message) =>
        readinessLog.push({ type: message.type(), text: message.text() })
      );
      page.on('pageerror', (err) => {
        error = `Scene error: ${err.message}`;
      });
      page.setDefaultTimeout(remaining());
      await page.goto(`http://127.0.0.1:${port}/mission-export.html`, {
        waitUntil: 'domcontentloaded',
        timeout: remaining(),
      });
      await page.waitForFunction(() => !!window.missionMap, undefined, {
        timeout: remaining(),
      });
      const plan = await page.evaluate(
        (raw) => window.missionMap.plan(raw),
        input
      );
      plannedViewIds.push(...plan.map((view) => view.id));
      for (let viewIndex = 0; viewIndex < plan.length; viewIndex++) {
        const viewStarted = performance.now();
        await page.evaluate(
          ({ input, viewIndex, digest }) =>
            window.missionMap.render(input, viewIndex, digest),
          { input, viewIndex, digest }
        );
        if (fault === 'context-loss') {
          await page.waitForSelector('canvas', { timeout: remaining() });
          await page.evaluate(() => {
            const canvas = document.querySelector('canvas');
            const gl = canvas.getContext('webgl2');
            gl.getExtension('WEBGL_lose_context').loseContext();
          });
        }
        try {
          await page.waitForFunction(
            () => window.missionMap.state.status !== 'loading',
            undefined,
            { timeout: remaining() }
          );
        } catch (err) {
          if (fault === 'slow' || performance.now() >= deadline - 100)
            throw new Error('Shared renderer deadline exceeded');
          throw err;
        }
        const readiness = await page.evaluate(() => window.missionMap.state);
        if (error || readiness.status !== 'ready')
          throw new Error(readiness.error ?? error ?? 'Readiness failed');
        if (
          readiness.digest !== digest ||
          readiness.viewId !== plan[viewIndex].id
        )
          throw new Error('Readiness identity mismatch');
        await page.waitForFunction(
          () =>
            document.querySelectorAll('[data-map-label]').length ===
            window.missionMap.state.labels.length,
          undefined,
          { timeout: remaining() }
        );
        const png = await page.screenshot({
          type: 'png',
          timeout: remaining(),
          animations: 'disabled',
        });
        const pixels = await page.evaluate(async (base64) => {
          const image = new Image();
          image.src = `data:image/png;base64,${base64}`;
          await image.decode();
          const canvas = document.createElement('canvas');
          canvas.width = image.width;
          canvas.height = image.height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(image, 0, 0);
          const data = ctx.getImageData(0, 0, image.width, image.height).data;
          const digest = await crypto.subtle.digest('SHA-256', data);
          const colors = new Set();
          for (let i = 0; i < data.length; i += 256)
            colors.add(`${data[i]},${data[i + 1]},${data[i + 2]}`);
          return {
            width: image.width,
            height: image.height,
            pixelHash: [...new Uint8Array(digest)]
              .map((b) => b.toString(16).padStart(2, '0'))
              .join(''),
            sampledColors: colors.size,
          };
        }, png.toString('base64'));
        if (
          pixels.width !== 1920 ||
          pixels.height !== 1080 ||
          pixels.sampledColors < 100
        )
          throw new Error('Blank or invalid primary PNG');
        const filename = `${legIndex}-${input.legId}-view-${viewIndex + 1}.png`;
        const pngPath = path.join(output, filename);
        await writeFile(pngPath, png);
        views.push({
          id: plan[viewIndex].id,
          inputDigest: digest,
          path: pngPath,
          pngHash: hash(png),
          ...pixels,
          readiness,
          seconds: (performance.now() - viewStarted) / 1000,
        });
        remaining();
      }
      await context.close();
      context = undefined;
    }
  } catch (err) {
    if (!error?.includes('deadline')) error = String(err);
  } finally {
    process.removeListener('SIGTERM', stop);
    process.removeListener('SIGINT', stop);
    process.stdin.removeListener('end', stop);
    process.stdin.pause();
    try {
      await context?.close();
      cleanup.contextsClosed = true;
    } catch (err) {
      cleanup.errors.push(String(err));
    }
    try {
      await browser?.close();
      await browserServer?.close();
    } catch (err) {
      cleanup.errors.push(String(err));
      await browserServer?.kill().catch(() => {});
    }
    const child = browserServer?.process();
    cleanup.browserExited =
      !child || child.exitCode !== null || child.signalCode !== null;
    if (!cleanup.browserExited) {
      await browserServer.kill();
      cleanup.browserExited =
        child.exitCode !== null || child.signalCode !== null;
    }
    try {
      if (server?.listening) {
        server.closeAllConnections();
        await new Promise((resolve, reject) =>
          server.close((err) => (err ? reject(err) : resolve()))
        );
      }
      cleanup.listenerClosed = !server?.listening;
    } catch (err) {
      cleanup.errors.push(String(err));
    }
    if (error) {
      for (const view of views) await rm(view.path, { force: true });
      views.length = 0;
    }
    await rm(path.join(output, 'browser-temp'), {
      recursive: true,
      force: true,
    });
    clearTimeout(watchdog);
    ownership.cleanup = cleanup;
    await recordOwnership();
  }
  const elapsedSeconds = (performance.now() - started) / 1000;
  if (elapsedSeconds > budgetSeconds && !error)
    error = 'Shared renderer deadline exceeded including cleanup';
  if (
    Object.values(cleanup).some((value) => value === false) ||
    cleanup.errors.length
  )
    error ??= 'Renderer cleanup failed';
  if (error && views.length) {
    for (const view of views) await rm(view.path, { force: true });
    views.length = 0;
  }
  const lock = JSON.parse(
    await readFile(new URL('../../package-lock.json', import.meta.url), 'utf8')
  );
  const versions = Object.fromEntries(
    ['react', 'three', '@react-three/fiber', 'playwright-core'].map((name) => [
      name,
      lock.packages[`node_modules/${name}`].version,
    ])
  );
  const sourceDigests = {};
  for (const name of [
    'main.tsx',
    'scene.tsx',
    'framing.ts',
    'protocol.ts',
    'render.mjs',
  ])
    sourceDigests[`frontend/mission-planner/src/mission-export/${name}`] = hash(
      await readFile(new URL(name, import.meta.url))
    );
  const assetDigests = {};
  for (const name of ['earth-day-hi.jpg', 'city-lights-mask.png'])
    assetDigests[name] = hash(await readFile(path.join(assetRoot, name)));
  for (const name of await readdir(path.join(assetRoot, 'assets')))
    assetDigests[`assets/${name}`] = hash(
      await readFile(path.join(assetRoot, 'assets', name))
    );
  const report = {
    inputs: legs,
    plannedViewIds,
    status: error ? 'fallback' : 'primary',
    fallbackLabel: error
      ? 'Overview map unavailable — static route fallback'
      : undefined,
    error,
    startupSeconds,
    elapsedSeconds,
    marginSeconds: 60 - elapsedSeconds,
    views,
    readinessLog,
    cleanup,
    ownership,
    runtime: {
      versions,
      sourceDigests,
      assetDigests,
      osRelease: await readFile('/etc/os-release', 'utf8'),
      browserRevision: JSON.parse(
        await readFile(
          new URL(
            '../../node_modules/playwright-core/browsers.json',
            import.meta.url
          ),
          'utf8'
        )
      ).browsers.find((b) => b.name === 'chromium-headless-shell'),
      osPackages: await readFile(
        '/opt/mission-map-os-packages.txt',
        'utf8'
      ).catch(() => 'local host check; use packaged gate OS manifest'),
      node: process.version,
      uid: process.getuid?.(),
      browser: browser?.version(),
      rendering: 'ANGLE SwiftShader; fixed 1920x1080 DPR 1',
    },
  };
  await writeFile(
    path.join(output, 'result.json'),
    JSON.stringify(report, null, 2)
  );
  return report;
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const [inputPath, output, assetRoot, fault] = process.argv.slice(2);
  console.log(JSON.stringify({ event: 'renderer-entry' }));
  const fixture = JSON.parse(await readFile(inputPath, 'utf8'));
  const result = await renderStage({
    legs: fixture.legs,
    output,
    assetRoot,
    fault,
    budgetSeconds: Number(process.env.MISSION_MAP_BUDGET_SECONDS ?? 57),
  });
  console.log(
    JSON.stringify({
      status: result.status,
      elapsedSeconds: result.elapsedSeconds,
      views: result.views.map((v) => v.id),
      error: result.error,
    })
  );
  process.exitCode = result.status === 'primary' ? 0 : 1;
}
