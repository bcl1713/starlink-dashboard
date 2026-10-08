import { mkdir, writeFile, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { createRenderBudget, within } from './render-budget.mjs';
import { openRenderOwner, ownedPath } from './render-owner.mjs';
import { renderMapInContext } from './map-stage.mjs';
import { verifyPdfInOwner } from './briefing-pdf-stage.mjs';
import {
  prepareMissionDocument,
  printMissionDocument,
} from './briefing-mission-layout.mjs';
const hash = (v) => createHash('sha256').update(v).digest('hex');
const error = (code, message) => Object.assign(new Error(message), { code });

/** One request owns all legs, print, verification and teardown under one clock. */
export async function renderMissionBriefing(
  {
    payload,
    outputRoot,
    assetRoot,
    ownershipPath = path.join(outputRoot, 'ownership.json'),
    budgetMs = 60000,
    pdfReserveMs = 20000,
    cleanupReserveMs = 3000,
    fault = null,
  },
  dependencies = {}
) {
  const budget = (dependencies.createBudget ?? createRenderBudget)({
    budgetMs,
    pdfReserveMs,
    cleanupReserveMs,
  });
  const openOwner = dependencies.openOwner ?? openRenderOwner;
  const mapStage = dependencies.mapStage ?? renderMapInContext;
  const documentStage = dependencies.documentStage ?? prepareMissionDocument;
  const printStage = dependencies.printStage ?? printMissionDocument;
  const verifyStage = dependencies.verifyStage ?? verifyPdfInOwner;
  outputRoot = path.resolve(outputRoot);
  const report = {
    schemaVersion: 2,
    status: 'failed',
    missionId: payload.missionId,
    snapshotFingerprint: payload.snapshotFingerprint,
    sharedBrowser: true,
    launchCount: 0,
    browserIdentity: null,
    maps: {},
    stages: {},
    fit: null,
    pagePlan: null,
    pdfValidation: null,
    artifactHashes: {},
    artifacts: null,
    cleanup: null,
    totalMs: 0,
    errorCode: null,
    reserves: {
      budgetMs,
      pdfMs: budget.pdfReserveMs,
      cleanupMs: budget.cleanupReserveMs,
    },
  };
  let owner,
    watchdog,
    cancelled = false,
    deadline = false,
    document;
  const stage = async (name, fn) => {
    const startMs = budget.elapsedMs();
    const journal = async (record) => {
      try {
        await writeFile(
          ownedPath(outputRoot, 'stage-progress.json'),
          JSON.stringify(record)
        );
      } catch (e) {
        if (name !== 'teardown') throw e;
        // Diagnostic I/O must never prevent release of the request owner.
        report.status = 'failed';
        report.errorCode ??= 'runtime';
        (report.journalErrors ??= []).push(String(e));
      }
    };
    try {
      await journal({
        stage: name,
        pid: process.pid,
        startMs,
        completed: false,
      });
      return await fn();
    } finally {
      report.stages[name] = {
        startMs,
        durationMs: budget.elapsedMs() - startMs,
      };
      await journal({
        stage: name,
        pid: process.pid,
        ...report.stages[name],
        completed: true,
      });
    }
  };
  const stop = () => {
    cancelled = true;
    void owner?.close();
  };
  const check = () => {
    if (cancelled) throw error('cancelled', 'Request cancelled');
    if (deadline) throw error('deadline', 'Shared deadline');
    budget.workRemainingMs();
  };
  process.once('SIGTERM', stop);
  process.once('SIGINT', stop);
  const pdfName = 'mission-customer-briefing-trial.pdf';
  const generated = [pdfName, 'mission-customer-briefing-trial.html'];
  try {
    await mkdir(outputRoot, { recursive: true });
    ownedPath(outputRoot, ownershipPath);
    if (
      payload.schemaVersion !== 2 ||
      !payload.legs?.length ||
      new Set(payload.legs.map((l) => l.legId)).size !== payload.legs.length
    )
      throw error('data', 'Invalid mission payload');
    watchdog = setTimeout(() => {
      deadline = true;
      void owner?.close();
    }, budget.workRemainingMs());
    await stage('startup', async () => {
      owner = await openOwner({
        assetRoot,
        outputRoot,
        ownershipPath,
        budget,
        fault,
      });
      return owner;
    });
    report.launchCount = 1;
    report.browserIdentity = owner.browserIdentity;
    check();
    let cutoff = false;
    for (const leg of payload.legs) {
      try {
        budget.mapRemainingMs();
      } catch {
        cutoff = true;
      }
      const map = cutoff
        ? {
            status: 'unavailable',
            pngs: [],
            warnings: ['Map reserve cutoff'],
            viewIds: [],
            framing: null,
            markers: [],
          }
        : await stage('map:' + leg.legId, () =>
            mapStage({ owner, budget, input: leg.mapInput, fault })
          );
      report.maps[leg.legId] = {
        ...map,
        inputDiagnostics: leg.mapInputDiagnostics,
      };
      check();
    }
    document = await stage('document', () =>
      documentStage({
        owner,
        budget,
        payload,
        maps: report.maps,
        outputRoot,
        fault,
        check,
        onDiagnostic: (name) => generated.push(name),
      })
    );
    report.pagePlan = document.pagePlan;
    report.fit = document.fit;
    report.assetHashes = document.assetHashes;
    report.artifactHashes = { ...document.diagnosticHashes };
    generated.push(...(document.diagnosticNames ?? []));
    check();
    const pdf = await stage('pdf', () =>
      within(printStage({ document, budget, fault }), budget.workRemainingMs())
    );
    await writeFile(ownedPath(outputRoot, pdfName), pdf);
    report.artifactHashes.pdfPath = hash(pdf);
    check();
    report.pdfValidation = await stage('verify', () =>
      verifyStage({
        owner,
        budget,
        pdfPath: ownedPath(outputRoot, pdfName),
        expectations: document.expectations,
        fault,
      })
    );
    check();
    await document.context?.close();
    report.status = 'success';
    report.artifacts = { pdfPath: pdfName };
  } catch (e) {
    report.errorCode = cancelled
      ? 'cancelled'
      : deadline
        ? 'deadline'
        : (e.code ?? 'runtime');
    report.error = String(e);
    if (e.cleanup) report.cleanup = e.cleanup;
  } finally {
    clearTimeout(watchdog);
    if (owner) {
      try {
        report.cleanup = await stage('teardown', () => owner.close());
      } catch (e) {
        report.cleanup = { success: false, errors: [String(e)] };
        report.errorCode = 'cleanup';
        report.status = 'failed';
      }
    }
    report.cleanup ??= {
      success: true,
      contextsClosed: true,
      browserExited: true,
      listenerClosed: true,
      survivors: [],
      errors: [],
      childrenReaped: true,
    };
    process.removeListener('SIGTERM', stop);
    process.removeListener('SIGINT', stop);
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
      for (const name of generated)
        await rm(ownedPath(outputRoot, name), { force: true });
    }
    for (const map of Object.values(report.maps)) delete map.pngs;
    await writeFile(
      ownedPath(outputRoot, 'render-report.json'),
      JSON.stringify(report, null, 2)
    );
  }
  return report;
}
