#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { access, lstat, mkdir, readFile, realpath, rename, rm, stat, writeFile } from 'node:fs/promises';
import { execFile as execFileCallback } from 'node:child_process';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { promisify } from 'node:util';

const execFile = promisify(execFileCallback);
const INSTALL_TIMEOUT_MS = 120_000;
const VERSION_TIMEOUT_MS = 10_000;
const MAX_COMMAND_OUTPUT_BYTES = 16 * 1024;
const LINUX_EXECUTABLE_PARTS = ['chrome-linux64', 'chrome'];
const FLAGS = new Set(['mode', 'project-dir', 'browser-root', 'task-root', 'provenance-file', 'npm-executable']);

function parseArgs(argv) {
  const values = {};
  for (let index = 2; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || value === undefined || value.startsWith('--') || !FLAGS.has(key.slice(2)) || values[key.slice(2)] !== undefined) throw new Error(`invalid argument: ${key}`);
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
  const playwrightPackagePath = join(projectDir, 'node_modules/playwright/package.json');
  const corePackagePath = join(projectDir, 'node_modules/playwright-core/package.json');
  const metadataPath = join(projectDir, 'node_modules/playwright-core/browsers.json');
  const [manifest, lock, installedPlaywright, installedCore, lockBytes] = await Promise.all([
    json(packagePath, 'package.json'),
    json(lockPath, 'package-lock.json'),
    json(playwrightPackagePath, 'installed playwright package.json'),
    json(corePackagePath, 'installed playwright-core package.json'),
    readFile(lockPath),
  ]);
  const declared = manifest.devDependencies?.['@playwright/test'];
  const rootDeclared = lock.packages?.['']?.devDependencies?.['@playwright/test'];
  const testPackage = lock.packages?.['node_modules/@playwright/test'];
  const playwrightPackage = lock.packages?.['node_modules/playwright'];
  const corePackage = lock.packages?.['node_modules/playwright-core'];
  if (!declared || declared !== rootDeclared || !/^\d+\.\d+\.\d+$/.test(declared)) throw new Error('package and lockfile must pin the same exact @playwright/test version');
  if (!testPackage || !playwrightPackage || !corePackage) throw new Error('package-lock lacks the pinned Playwright package chain');
  if (testPackage.version !== declared || playwrightPackage.version !== declared || corePackage.version !== declared || testPackage.dependencies?.playwright !== declared || playwrightPackage.dependencies?.['playwright-core'] !== declared) throw new Error('package-lock Playwright package chain does not match the pinned version');
  if (installedPlaywright.version !== playwrightPackage.version) throw new Error('installed playwright version does not match package-lock');
  if (installedCore.version !== corePackage.version) throw new Error('installed playwright-core version does not match package-lock');
  const [metadata, metadataBytes] = await Promise.all([json(metadataPath, 'playwright browser metadata'), readFile(metadataPath)]);
  const chromium = metadata.browsers?.find((browser) => browser.name === 'chromium');
  if (!chromium || !/^\d+$/.test(chromium.revision) || !/^\d+(?:\.\d+){3}$/.test(chromium.browserVersion ?? '')) throw new Error('locked Playwright browser metadata lacks a valid Chromium revision/version');
  return {
    lockfile: { path: lockPath, sha256: sha256(lockBytes) },
    playwright: { version: declared, integrity: testPackage.integrity ?? null, coreIntegrity: corePackage.integrity ?? null, installedVersion: installedPlaywright.version, installedCoreVersion: installedCore.version },
    chromium: { revision: chromium.revision, version: chromium.browserVersion, metadataPath, metadataSha256: sha256(metadataBytes) },
  };
}

function installerCommand(projectDir) {
  return [process.execPath, join(projectDir, 'node_modules/playwright/cli.js'), 'install', 'chromium'];
}

async function trustedPlaywrightCli(projectDir) {
  const cli = join(projectDir, 'node_modules/playwright/cli.js');
  const info = await lstat(cli);
  if (info.isSymbolicLink() || !info.isFile()) throw new Error('Playwright CLI must be a non-symlink regular file');
  if (await realpath(cli) !== cli || !inside(projectDir, cli).startsWith(resolve(projectDir))) throw new Error('Playwright CLI must not resolve outside the project');
  return cli;
}

async function npmIdentity(npmExecutable) {
  const npm = resolve(npmExecutable);
  const info = await lstat(npm);
  if (info.isSymbolicLink() || !info.isFile()) throw new Error('npm executable must be a non-symlink regular file');
  if (await realpath(npm) !== npm) throw new Error('npm executable must not resolve through a symlink');
  await access(npm, constants.R_OK | constants.X_OK);
  let versionOutput;
  try {
    versionOutput = (await execFile(npm, ['--version'], { timeout: VERSION_TIMEOUT_MS, maxBuffer: MAX_COMMAND_OUTPUT_BYTES })).stdout.trim();
  } catch (error) {
    throw new Error(`cannot execute npm executable: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!/^\d+(?:\.\d+){1,2}(?:[-+][0-9A-Za-z.-]+)?$/.test(versionOutput)) throw new Error(`npm executable returned an invalid version: ${bounded(versionOutput)}`);
  return { path: npm, sha256: sha256(await readFile(npm)), size: info.size, versionOutput: bounded(versionOutput) };
}

async function playwrightCliIdentity(projectDir) {
  const cli = await trustedPlaywrightCli(projectDir);
  const info = await stat(cli);
  return { path: cli, dev: String(info.dev), ino: String(info.ino), ctimeMs: info.ctimeMs, size: info.size, sha256: sha256(await readFile(cli)) };
}

async function existingPlaywrightCliIdentity(projectDir) {
  try {
    return await playwrightCliIdentity(projectDir);
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
}

function sameCliIdentity(left, right) {
  return left?.path === right?.path && left?.dev === right?.dev && left?.ino === right?.ino && left?.ctimeMs === right?.ctimeMs && left?.size === right?.size && left?.sha256 === right?.sha256;
}

async function prepareLockedPackages(projectDir, npmExecutable) {
  const lockPath = join(projectDir, 'package-lock.json');
  const before = await readFile(lockPath);
  const npm = await npmIdentity(npmExecutable);
  const beforeCli = await existingPlaywrightCliIdentity(projectDir);
  const command = [npm.path, 'ci', '--ignore-scripts'];
  try {
    const result = await execFile(command[0], command.slice(1), {
      cwd: projectDir,
      env: { ...process.env, NPM_CONFIG_IGNORE_SCRIPTS: 'true' },
      timeout: INSTALL_TIMEOUT_MS,
      maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
    });
    const after = await readFile(lockPath);
    if (!after.equals(before)) throw new Error('npm ci changed package-lock.json');
    const preparedCli = beforeCli ? await playwrightCliIdentity(projectDir) : null;
    if (beforeCli && sameCliIdentity(beforeCli, preparedCli)) throw new Error('npm ci did not replace Playwright CLI');
    return { record: { command, executable: npm, lockfileSha256: sha256(before), stdout: bounded(result.stdout), stderr: bounded(result.stderr) }, preparedCli };
  } catch (error) {
    const output = [error.stdout, error.stderr].filter(Boolean).map(bounded).join('\n');
    throw new Error(`locked npm ci --ignore-scripts preparation failed: ${error instanceof Error ? error.message : String(error)}${output ? `\n${output}` : ''}`);
  }
}

async function install(projectDir, browserRoot, preparedCli) {
  const command = installerCommand(projectDir);
  const [file, ...args] = command;
  const cliIdentity = await playwrightCliIdentity(projectDir);
  if (preparedCli && !sameCliIdentity(preparedCli, cliIdentity)) throw new Error('Playwright CLI changed after npm ci');
  const cli = cliIdentity.path;
  if (args[0] !== cli) throw new Error('Playwright CLI command does not match the trusted project entrypoint');
  await access(cli, constants.R_OK);
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

async function provenanceDestination(taskRoot, provenanceFile) {
  const root = resolve(taskRoot);
  const target = inside(root, provenanceFile);
  const rootInfo = await lstat(root);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) throw new Error('task root must be a non-symlink directory');
  const canonicalRoot = await realpath(root);
  let cursor = canonicalRoot;
  const parts = relative(root, target).split('/');
  for (const part of parts.slice(0, -1)) {
    cursor = join(cursor, part);
    try {
      const info = await lstat(cursor);
      if (info.isSymbolicLink()) throw new Error(`provenance path contains a symlink: ${cursor}`);
      if (!info.isDirectory()) throw new Error(`provenance path parent is not a directory: ${cursor}`);
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
      await mkdir(cursor, { mode: 0o700 });
    }
  }
  try {
    const targetInfo = await lstat(target);
    if (targetInfo.isSymbolicLink()) throw new Error(`provenance file is a symlink: ${target}`);
    if (!targetInfo.isFile()) throw new Error(`provenance target is not a regular file: ${target}`);
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  return target;
}

async function writeProvenanceAtomically(taskRoot, provenanceFile, result) {
  const target = await provenanceDestination(taskRoot, provenanceFile);
  const temporary = join(dirname(target), `.${basename(target)}.${process.pid}.${Date.now()}.tmp`);
  await writeFile(temporary, `${JSON.stringify(result, null, 2)}\n`, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
  try {
    await rename(temporary, target);
  } catch (error) {
    await rm(temporary, { force: true }).catch(() => {});
    throw error;
  }
}

async function main() {
  const flags = parseArgs(process.argv);
  const mode = required(flags, 'mode');
  if (!['verify', 'provision'].includes(mode)) throw new Error('--mode must be verify or provision');
  if (process.platform !== 'linux') throw new Error(`unsupported provision platform: ${process.platform}`);
  const projectDir = resolve(required(flags, 'project-dir'));
  const browserRoot = resolve(required(flags, 'browser-root'));
  const taskRoot = resolve(required(flags, 'task-root'));
  const provenanceFile = resolve(required(flags, 'provenance-file'));
  const npmExecutable = mode === 'provision' ? resolve(required(flags, 'npm-executable')) : null;
  const preparedPackages = mode === 'provision' ? await prepareLockedPackages(projectDir, npmExecutable) : null;
  const packagePreparation = preparedPackages?.record ?? null;
  const locked = await lockedBrowser(projectDir);
  const executablePath = inside(browserRoot, join(browserRoot, `chromium-${locked.chromium.revision}`, ...LINUX_EXECUTABLE_PARTS));
  let installer = null;
  let executable;
  if (mode === 'provision') {
    try {
      executable = await verifyExecutable(executablePath, locked.chromium.version);
    } catch {
      installer = await install(projectDir, browserRoot, preparedPackages?.preparedCli);
      executable = await verifyExecutable(executablePath, locked.chromium.version);
    }
  } else {
    executable = await verifyExecutable(executablePath, locked.chromium.version);
  }
  const result = { status: 'passed', mode, projectDir, browserRoot, taskRoot, packagePreparation, ...locked, executable, installer };
  await writeProvenanceAtomically(taskRoot, provenanceFile, result);
  return result;
}

main().then(
  (result) => process.stdout.write(`${JSON.stringify(result)}\n`),
  (error) => {
    process.stdout.write(`${JSON.stringify({ status: 'failed', error: error instanceof Error ? error.message : String(error) })}\n`);
    process.exitCode = 1;
  },
);
