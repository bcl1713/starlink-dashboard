#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { access, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { execFile as execFileCallback } from 'node:child_process';
import { dirname, join, relative, resolve } from 'node:path';
import { promisify } from 'node:util';

const execFile = promisify(execFileCallback);
const INSTALL_TIMEOUT_MS = 120_000;
const VERSION_TIMEOUT_MS = 10_000;
const MAX_COMMAND_OUTPUT_BYTES = 16 * 1024;
const LINUX_EXECUTABLE_PARTS = ['chrome-linux64', 'chrome'];

function parseArgs(argv) {
  const values = {};
  for (let index = 2; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || value === undefined || value.startsWith('--')) throw new Error(`invalid argument: ${key}`);
    values[key.slice(2)] = value;
  }
  return values;
}

function required(flags, name) {
  const value = flags[name];
  if (!value) throw new Error(`missing --${name}`);
  return value;
}

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function bounded(value) {
  const bytes = Buffer.from(String(value));
  return bytes.length <= MAX_COMMAND_OUTPUT_BYTES
    ? bytes.toString('utf8')
    : `${bytes.subarray(0, MAX_COMMAND_OUTPUT_BYTES - 32).toString('utf8')}…[truncated]`;
}

function inside(root, target) {
  const resolvedRoot = resolve(root);
  const resolvedTarget = resolve(target);
  if (relative(resolvedRoot, resolvedTarget).startsWith('..')) throw new Error(`path escapes its required root: ${resolvedTarget}`);
  return resolvedTarget;
}

async function json(path, label) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch (error) {
    throw new Error(`cannot read ${label}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function lockedBrowser(projectDir) {
  const packagePath = join(projectDir, 'package.json');
  const lockPath = join(projectDir, 'package-lock.json');
  const metadataPath = join(projectDir, 'node_modules/playwright-core/browsers.json');
  const [manifest, lock, metadata, lockBytes, metadataBytes] = await Promise.all([
    json(packagePath, 'package.json'),
    json(lockPath, 'package-lock.json'),
    json(metadataPath, 'playwright browser metadata'),
    readFile(lockPath),
    readFile(metadataPath),
  ]);
  const declared = manifest.devDependencies?.['@playwright/test'];
  const rootDeclared = lock.packages?.['']?.devDependencies?.['@playwright/test'];
  const testPackage = lock.packages?.['node_modules/@playwright/test'];
  const playwrightPackage = lock.packages?.['node_modules/playwright'];
  const corePackage = lock.packages?.['node_modules/playwright-core'];
  if (!declared || declared !== rootDeclared || !/^\d+\.\d+\.\d+$/.test(declared)) throw new Error('package and lockfile must pin the same exact @playwright/test version');
  if (!testPackage || !playwrightPackage || !corePackage) throw new Error('package-lock lacks the pinned Playwright package chain');
  if (testPackage.version !== declared || playwrightPackage.version !== declared || corePackage.version !== declared || testPackage.dependencies?.playwright !== declared || playwrightPackage.dependencies?.['playwright-core'] !== declared) throw new Error('package-lock Playwright package chain does not match the pinned version');
  const chromium = metadata.browsers?.find((browser) => browser.name === 'chromium');
  if (!chromium || !/^\d+$/.test(chromium.revision) || !/^\d+(?:\.\d+){3}$/.test(chromium.browserVersion ?? '')) throw new Error('locked Playwright browser metadata lacks a valid Chromium revision/version');
  return {
    lockfile: { path: lockPath, sha256: sha256(lockBytes) },
    playwright: { version: declared, integrity: testPackage.integrity ?? null, coreIntegrity: corePackage.integrity ?? null },
    chromium: { revision: chromium.revision, version: chromium.browserVersion, metadataPath, metadataSha256: sha256(metadataBytes) },
  };
}

function installerCommand(flags, projectDir) {
  if (!flags['installer-command-json']) return [process.execPath, join(projectDir, 'node_modules/playwright/cli.js'), 'install', 'chromium'];
  let command;
  try {
    command = JSON.parse(flags['installer-command-json']);
  } catch {
    throw new Error('--installer-command-json must be a JSON command array');
  }
  if (!Array.isArray(command) || command.length === 0 || command.some((part) => typeof part !== 'string' || !part)) throw new Error('--installer-command-json must be a non-empty string array');
  return command;
}

async function install(command, projectDir, browserRoot) {
  const [file, ...args] = command;
  try {
    const result = await execFile(file, args, {
      cwd: projectDir,
      env: { ...process.env, PLAYWRIGHT_BROWSERS_PATH: browserRoot },
      timeout: INSTALL_TIMEOUT_MS,
      maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
    });
    return { command, stdout: bounded(result.stdout), stderr: bounded(result.stderr) };
  } catch (error) {
    const output = [error.stdout, error.stderr].filter(Boolean).map(bounded).join('\n');
    throw new Error(`Chromium installer failed: ${error instanceof Error ? error.message : String(error)}${output ? `\n${output}` : ''}`);
  }
}

async function verifyExecutable(path, expectedVersion) {
  await access(path, constants.X_OK);
  const details = await stat(path);
  if (!details.isFile()) throw new Error(`expected executable is not a file: ${path}`);
  let versionOutput;
  try {
    versionOutput = (await execFile(path, ['--version'], { timeout: VERSION_TIMEOUT_MS, maxBuffer: MAX_COMMAND_OUTPUT_BYTES })).stdout.trim();
  } catch (error) {
    throw new Error(`cannot execute expected Chromium: ${error instanceof Error ? error.message : String(error)}`);
  }
  const versionMatch = versionOutput.match(/\b\d+(?:\.\d+){3}\b/);
  if (versionMatch?.[0] !== expectedVersion) throw new Error(`Chromium version mismatch: expected ${expectedVersion}, got ${bounded(versionOutput)}`);
  return { path, versionOutput: bounded(versionOutput), sha256: sha256(await readFile(path)), size: details.size };
}

async function main() {
  const flags = parseArgs(process.argv);
  const mode = required(flags, 'mode');
  if (!['verify', 'provision'].includes(mode)) throw new Error('--mode must be verify or provision');
  if (process.platform !== 'linux') throw new Error(`unsupported provision platform: ${process.platform}`);
  const projectDir = resolve(required(flags, 'project-dir'));
  const browserRoot = resolve(required(flags, 'browser-root'));
  const provenanceFile = resolve(required(flags, 'provenance-file'));
  await rm(provenanceFile, { force: true });
  const locked = await lockedBrowser(projectDir);
  const executablePath = inside(browserRoot, join(browserRoot, `chromium-${locked.chromium.revision}`, ...LINUX_EXECUTABLE_PARTS));
  let installer = null;
  let executable;
  if (mode === 'provision') {
    try {
      executable = await verifyExecutable(executablePath, locked.chromium.version);
    } catch {
      installer = await install(installerCommand(flags, projectDir), projectDir, browserRoot);
      executable = await verifyExecutable(executablePath, locked.chromium.version);
    }
  } else {
    executable = await verifyExecutable(executablePath, locked.chromium.version);
  }
  const result = {
    status: 'passed',
    mode,
    projectDir,
    browserRoot,
    ...locked,
    executable,
    installer,
  };
  await mkdir(dirname(provenanceFile), { recursive: true, mode: 0o700 });
  await writeFile(provenanceFile, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
  return result;
}

main().then(
  (result) => process.stdout.write(`${JSON.stringify(result)}\n`),
  async (error) => {
    process.stdout.write(`${JSON.stringify({ status: 'failed', error: error instanceof Error ? error.message : String(error) })}\n`);
    process.exitCode = 1;
  },
);
