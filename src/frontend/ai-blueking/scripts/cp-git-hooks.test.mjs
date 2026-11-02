import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

const env = { ...process.env, GIT_CONFIG_GLOBAL: '/dev/null', GIT_CONFIG_NOSYSTEM: '1' };
const hook = '#!/bin/sh\nprintf "fixture hook ran\\n" > .hook-ran\n';
const git = (cwd, ...args) => execFileSync('git', args, { cwd, env, encoding: 'utf-8' }).trim();

const setup = t => {
  const root = mkdtempSync(join(tmpdir(), 'cp-git-hooks-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const repo = join(root, 'repo');
  mkdirSync(repo);
  git(repo, 'init', '--quiet');
  git(repo, '-c', 'user.name=Hook Test', '-c', 'user.email=hooks@example.test',
    'commit', '--quiet', '--allow-empty', '-m', 'initial');
  return { root, repo };
};

const runCopy = repo => {
  const monorepo = join(repo, 'src', 'frontend', 'ai-blueking');
  const scripts = join(monorepo, 'scripts');
  const localHooks = join(monorepo, '.git', 'hooks');
  mkdirSync(scripts, { recursive: true });
  mkdirSync(localHooks, { recursive: true });
  copyFileSync(join(import.meta.dirname, 'cp-git-hooks.mjs'), join(scripts, 'cp-git-hooks.mjs'));
  writeFileSync(join(localHooks, 'pre-commit'), hook, { mode: 0o755 });
  const result = spawnSync(process.execPath, [join(scripts, 'cp-git-hooks.mjs')], {
    cwd: monorepo, env, encoding: 'utf-8',
  });
  assert.equal(result.status, 0, result.stderr);
};

const assertHook = (repo, hooksDir) => {
  assert.equal(readFileSync(join(hooksDir, 'pre-commit'), 'utf-8'), hook);
  git(repo, 'hook', 'run', 'pre-commit');
  assert.equal(readFileSync(join(repo, '.hook-ran'), 'utf-8'), 'fixture hook ran\n');
};

test('普通仓库：安装到 Git hooks 目录并可执行', t => {
  const { repo } = setup(t);
  runCopy(repo);
  assertHook(repo, join(repo, '.git', 'hooks'));
});

test('linked worktree：安装到共享 hooks 目录并可执行', t => {
  const { root, repo } = setup(t);
  const worktree = join(root, 'linked');
  git(repo, 'worktree', 'add', '--quiet', '--detach', worktree);
  runCopy(worktree);
  assertHook(worktree, join(repo, '.git', 'hooks'));
});

test('目标 hooks 目录不存在时仍可安装', t => {
  const { repo } = setup(t);
  const hooksDir = join(repo, '.git', 'hooks');
  rmSync(hooksDir, { recursive: true, force: true });
  runCopy(repo);
  assertHook(repo, hooksDir);
});
