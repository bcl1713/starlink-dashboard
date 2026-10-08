import { readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createRenderBudget, within } from './render-budget.mjs';
import { openRenderOwner, ownedPath } from './render-owner.mjs';
import { renderMapInContext } from './map-stage.mjs';
import { composeBriefing } from './briefing/document.mjs';
import { buildPdfExpectations } from './briefing/pdf-expectations.mjs';

const hash = (v) => createHash('sha256').update(v).digest('hex');
const here = path.dirname(fileURLToPath(import.meta.url));
const stem = 'mission-customer-briefing-trial';
const error = (code, message) => Object.assign(new Error(message), { code });
export async function renderBriefing({
  payload,
  outputRoot,
  assetRoot,
  ownershipPath = path.join(outputRoot, 'ownership.json'),
  budgetMs = 60000,
  pdfReserveMs = 20000,
  cleanupReserveMs = 3000,
  fault = null,
}) {
  const budget = createRenderBudget({
    budgetMs,
    pdfReserveMs,
    cleanupReserveMs,
  });
  outputRoot = path.resolve(outputRoot);
  ownershipPath = path.resolve(ownershipPath);
  let owner,
    watchdog,
    cancelled = false,
    deadline = false;
  const report = {
    schemaVersion: 1,
    status: 'failed',
    legId: payload.legId,
    snapshotFingerprint: payload.snapshotFingerprint,
    sharedBrowser: true,
    launchCount: 0,
    browserIdentity: null,
    assetHashes: {},
    map: null,
    fit: null,
    stages: {},
    totalMs: 0,
    cleanup: null,
    errorCode: null,
    artifacts: null,
    reserves: { pdfMs: pdfReserveMs, cleanupMs: cleanupReserveMs, budgetMs },
  };
  const stage = async (name, fn) => {
    const start = budget.elapsedMs();
    try {
      return await fn();
    } finally {
      report.stages[name] = {
        startMs: start,
        durationMs: budget.elapsedMs() - start,
      };
    }
  };
  const check = () => {
    if (cancelled) throw error('cancelled', 'Render cancelled');
    if (deadline) throw error('deadline', 'Shared deadline');
    budget.workRemainingMs();
  };
  const stop = () => {
    cancelled = true;
    void owner?.close();
  };
  process.once('SIGTERM', stop);
  process.once('SIGINT', stop);
  await mkdir(outputRoot, { recursive: true });
  const names = {
    htmlPath: `${stem}.html`,
    pngPath: `${stem}.png`,
    pdfPath: `${stem}.pdf`,
  };
  try {
    if (
      payload.schemaVersion !== 1 ||
      !payload.rows ||
      !payload.flight ||
      !payload.intervals?.length
    )
      throw error('payload', 'Invalid payload');
    ownedPath(outputRoot, ownershipPath);
    watchdog = setTimeout(() => {
      deadline = true;
      void owner?.close();
    }, budget.workRemainingMs());
    await stage('startup', async () => {
      report.launchCount = fault === 'startup' ? 0 : 1;
      owner = await openRenderOwner({
        assetRoot,
        outputRoot,
        ownershipPath,
        budget,
        fault,
      });
      report.browserIdentity = owner.browserIdentity;
    });
    check();
    report.map = await stage('map', () =>
      renderMapInContext({ owner, budget, input: payload.mapInput, fault })
    );
    check();
    let context, page, html;
    await stage('html', async () => {
      const paths = {
        regularFont:
          process.env.BRIEFING_REGULAR_FONT ||
          '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        boldFont:
          process.env.BRIEFING_BOLD_FONT ||
          '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        apo:
          process.env.BRIEFING_APO_PATH ||
          path.resolve(
            '../../backend/starlink-location/app/mission/assets/APO Patch.jpg'
          ),
        css: path.join(here, 'briefing', 'briefing.css'),
      };
      const assets = {};
      for (const [key, file] of Object.entries(paths)) {
        const bytes = await readFile(file);
        report.assetHashes[key] = hash(bytes);
        assets[key] = bytes;
      }
      const encoded = (key, type) =>
        `data:${type};base64,${assets[key].toString('base64')}`;
      html = composeBriefing(payload, {
        mapDataUrl: report.map.pngs[0] || null,
        apoDataUrl: encoded('apo', 'image/jpeg'),
        regularFontDataUrl: encoded('regularFont', 'font/ttf'),
        boldFontDataUrl: encoded('boldFont', 'font/ttf'),
        cssText: assets.css.toString(),
      });
      context = await owner.newContext({
        viewport: { width: 1280, height: 720 },
        deviceScaleFactor: 2.5,
        locale: 'en-US',
        timezoneId: 'America/New_York',
        reducedMotion: 'reduce',
      });
      let blocked = false;
      await context.route('**/*', (route) => {
        blocked = true;
        return route.abort('blockedbyclient');
      });
      page = await context.newPage();
      await page.emulateMedia({ media: 'print' });
      if (fault === 'font')
        html = html
          .replaceAll(
            encoded('regularFont', 'font/ttf'),
            'data:font/ttf;base64,broken'
          )
          .replaceAll(
            encoded('boldFont', 'font/ttf'),
            'data:font/ttf;base64,broken'
          );
      if (fault === 'image')
        html = html.replace(
          encoded('apo', 'image/jpeg'),
          'data:image/png;base64,broken'
        );
      if (fault === 'remote')
        html = html.replace(
          encoded('apo', 'image/jpeg'),
          'https://checkpoint.invalid/apo.png'
        );
      await page.setContent(html, {
        waitUntil: 'domcontentloaded',
        timeout: budget.workRemainingMs(),
      });
      if (fault === 'traversal') {
        const response = await context.request.get(
          `${owner.origin}/..%2foutside-owned-root`,
          { timeout: budget.workRemainingMs() }
        );
        if (response.status() !== 404)
          throw error('resource', 'Asset traversal admitted');
        throw error('resource', 'Asset traversal rejected');
      }
      const readiness = await within(
        page.evaluate(async () => {
          await document.fonts.ready;
          let fonts = true;
          try {
            await document.fonts.load('400 20px Briefing');
            await document.fonts.load('700 20px Briefing');
          } catch {
            fonts = false;
          }
          fonts =
            fonts &&
            [...document.fonts].length === 2 &&
            [...document.fonts].every((f) => f.status === 'loaded');
          const images = await Promise.all(
            [...document.images].map(async (i) => {
              try {
                await i.decode();
                return i.naturalWidth > 0;
              } catch {
                return false;
              }
            })
          );
          return {
            fonts,
            images: images.every(Boolean),
            ready:
              document.querySelector('.briefing-page')?.dataset.ready ===
              'true',
          };
        }),
        budget.workRemainingMs()
      );
      if (blocked || fault === 'remote')
        throw error('resource', 'Remote assets rejected');
      if (!readiness.fonts) throw error('font', 'Intended fonts did not load');
      if (!readiness.images)
        throw error('image', 'Document image decode failed');
      if (!readiness.ready) throw error('fit', 'Composition not ready');
      if (fault === 'overflow-title')
        await page
          .locator('h1')
          .evaluate(
            (e) => (e.textContent = 'Oversized checkpoint title '.repeat(100))
          );
      if (fault === 'overflow-table')
        await page
          .locator('tbody')
          .evaluate((e) => (e.innerHTML = e.innerHTML.repeat(10)));
      report.fit = await page.evaluate(() => {
        const page = document.querySelector('.briefing-page'),
          p = page.getBoundingClientRect();
        const bounds = (e) => {
          const r = e.getBoundingClientRect();
          return {
            x: r.x,
            y: r.y,
            width: r.width,
            height: r.height,
            right: r.right,
            bottom: r.bottom,
          };
        };
        const overflow = [];
        const markers = [];
        for (const e of document.querySelectorAll(
          '[data-fit],[data-svg-label]'
        )) {
          const r = e.getBoundingClientRect();
          if (
            r.left < p.left - 0.5 ||
            r.right > p.right + 0.5 ||
            r.top < p.top - 0.5 ||
            r.bottom > p.bottom + 0.5 ||
            (e.scrollWidth > e.clientWidth + 1 && !(e instanceof SVGElement)) ||
            (e.scrollHeight > e.clientHeight + 1 && !(e instanceof SVGElement))
          )
            overflow.push({
              tag: e.tagName,
              text: e.textContent.slice(0, 80),
              bounds: bounds(e),
            });
          if (e.hasAttribute('data-svg-label'))
            markers.push({ text: e.textContent, bounds: bounds(e) });
        }
        const labelOverlaps = [];
        for (let i = 0; i < markers.length; i++) {
          for (let j = i + 1; j < markers.length; j++) {
            const a = markers[i].bounds,
              b = markers[j].bounds;
            if (
              Math.min(a.right, b.right) - Math.max(a.x, b.x) > 1 &&
              Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > 1
            )
              labelOverlaps.push([markers[i].text, markers[j].text]);
          }
        }
        const remainingLines = [
          ...document.querySelectorAll('.remaining-cell'),
        ].map((cell) => {
          const range = document.createRange();
          range.selectNodeContents(cell);
          return {
            text: cell.textContent,
            lines: new Set([...range.getClientRects()].map((r) => r.top)).size,
            fontPx: parseFloat(getComputedStyle(cell).fontSize),
          };
        });
        const red = document.querySelector(
          '[data-posture="Communications unavailable"]'
        );
        const localBox = (e) => {
          const r = e.getBoundingClientRect();
          return [
            r.left - p.left,
            r.top - p.top,
            r.right - p.left,
            r.bottom - p.top,
          ];
        };
        const tableRows = [...document.querySelectorAll('[data-row-id]')];
        const pdfMeasured = {
          tableBodyBoundsPx: tableRows.length
            ? localBox(document.querySelector('tbody'))
            : null,
          rows: tableRows.map((r) => ({
            id: r.dataset.rowId,
            cellBoundsPx: [...r.cells].map(localBox),
          })),
        };
        return {
          pdfMeasured,
          page: bounds(page),
          pageCount: 1,
          visibleRowIds: [...document.querySelectorAll('[data-row-id]')].map(
            (e) => e.dataset.rowId
          ),
          fonts: ['Briefing 400', 'Briefing 700'],
          labels: markers,
          labelOverlaps,
          remainingLines,
          overflow,
          redFraction: red ? red.getBBox().width / 960 : null,
          postures: [...document.querySelectorAll('[data-posture]')].map(
            (e) => e.dataset.posture
          ),
          noticeCount: document.querySelectorAll('.notice').length,
          mapCount: document.querySelectorAll('.map-card').length,
        };
      });
      if (payload.rows.every((r) => r.displayCells)) {
        report.fit.pdfExpectations = buildPdfExpectations(
          payload,
          report.fit.pdfMeasured
        );
      }
      if (
        report.fit.overflow.length ||
        report.fit.labelOverlaps.length ||
        report.fit.page.width !== 1280 ||
        report.fit.page.height !== 720 ||
        JSON.stringify(report.fit.visibleRowIds) !==
          JSON.stringify(payload.rows.map((r) => r.id))
      ) {
        await page.locator('.briefing-page').screenshot({
          path: ownedPath(outputRoot, 'fit-failure.png'),
          timeout: budget.workRemainingMs(),
        });
        throw error('fit', 'Page fit failed');
      }
      const png = await page.locator('.briefing-page').screenshot({
        type: 'png',
        animations: 'disabled',
        timeout: budget.workRemainingMs(),
      });
      await writeFile(ownedPath(outputRoot, names.htmlPath), html);
      await writeFile(ownedPath(outputRoot, names.pngPath), png);
      check();
    });
    await stage('pdf', async () => {
      if (fault?.startsWith('pdf-row-')) {
        await page.locator('tbody').evaluate((body, damage) => {
          const rows = [...body.rows];
          const row = rows[Math.floor(rows.length / 2)];
          if (damage === 'pdf-row-missing') row.remove();
          if (damage === 'pdf-row-duplicate') body.append(row.cloneNode(true));
          if (damage === 'pdf-row-swapped') body.insertBefore(rows[1], rows[0]);
          if (damage === 'pdf-row-changed')
            row.cells[2].textContent = 'Unexpected capability';
          if (damage === 'pdf-row-split')
            row.style.transform = 'translateY(500px)';
        }, fault);
      }
      if (fault === 'print') throw error('print', 'Injected PDF rejection');
      if (fault === 'print-hang')
        await within(new Promise(() => {}), budget.workRemainingMs());
      const pdf = await within(
        page.pdf({
          width: '13.333333in',
          height: '7.5in',
          scale: 1,
          margin: { top: '0', right: '0', bottom: '0', left: '0' },
          printBackground: true,
          displayHeaderFooter: false,
          preferCSSPageSize: true,
        }),
        budget.workRemainingMs()
      );
      await writeFile(ownedPath(outputRoot, names.pdfPath), pdf);
      check();
      await context.close();
    });
    report.status = 'success';
    report.artifacts = names;
  } catch (e) {
    report.errorCode = cancelled
      ? 'cancelled'
      : deadline
        ? 'deadline'
        : e.code || 'render';
    report.error = String(e);
    if (e.cleanup) report.cleanup = e.cleanup;
  } finally {
    clearTimeout(watchdog);
    process.removeListener('SIGTERM', stop);
    process.removeListener('SIGINT', stop);
    await stage('teardown', async () => {
      if (owner) report.cleanup = await owner.close();
    });
    report.cleanup ??= {
      success: true,
      contextsClosed: true,
      browserExited: true,
      listenerClosed: true,
      survivors: [],
      errors: [],
      contextCount: 0,
      childrenReaped: true,
    };
    if (report.status === 'success' && report.artifacts) {
      report.artifactHashes = {};
      for (const [key, name] of Object.entries(names))
        report.artifactHashes[key] = hash(
          await readFile(ownedPath(outputRoot, name))
        );
    }
    report.totalMs = budget.elapsedMs();
    if (!report.cleanup.success || fault === 'cleanup') {
      report.status = 'failed';
      report.errorCode = 'cleanup';
    }
    if (report.totalMs > budgetMs) {
      report.status = 'failed';
      report.errorCode = 'deadline';
    }
    if (report.status !== 'success') {
      report.artifacts = null;
      for (const name of Object.values(names))
        await rm(ownedPath(outputRoot, name), { force: true });
    }
    const map = report.map;
    if (map) report.map = { ...map, pngs: undefined };
    await writeFile(
      ownedPath(outputRoot, 'render-report.json'),
      JSON.stringify(report, null, 2)
    );
  }
  return report;
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const [input, outputRoot, assetRoot] = process.argv.slice(2);
  const payload = JSON.parse(await readFile(input, 'utf8'));
  const budgetMs = Number(process.env.CHECKPOINT_BUDGET_MS || 60000);
  const options =
    budgetMs === 60000
      ? {}
      : {
          pdfReserveMs: Math.floor(budgetMs * 0.5),
          cleanupReserveMs: Math.floor(budgetMs * 0.1),
        };
  const report = await renderBriefing({
    payload,
    outputRoot,
    assetRoot,
    budgetMs,
    ...options,
    fault: process.env.CHECKPOINT_FAULT || null,
  });
  process.stdout.write(JSON.stringify(report) + '\n');
  process.exitCode = report.status === 'success' ? 0 : 1;
}
