import { execSync } from 'node:child_process';
import { copyFileSync, existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const MONOREPO_DIR = resolve(import.meta.dirname, '..');
const LOCAL_HOOKS_DIR = join(MONOREPO_DIR, '.git', 'hooks');

/** 通过 git 命令定位真实的 .git/hooks 目录 */
const getGitHooksDir = () => {
  const gitDir = execSync('git rev-parse --git-dir', { cwd: MONOREPO_DIR, encoding: 'utf-8' }).trim();
  return join(resolve(MONOREPO_DIR, gitDir), 'hooks');
};

const run = () => {
  if (!existsSync(LOCAL_HOOKS_DIR)) {
    console.log('[cp-git-hooks] 本地 .git/hooks 不存在，请先执行 simple-git-hooks');
    return;
  }

  const targetDir = getGitHooksDir();

  if (LOCAL_HOOKS_DIR === targetDir) {
    console.log('[cp-git-hooks] 本地 hooks 目录与目标目录相同，无需拷贝');
    return;
  }

  const hooks = readdirSync(LOCAL_HOOKS_DIR).filter(name => {
    const fullPath = join(LOCAL_HOOKS_DIR, name);
    return statSync(fullPath).isFile() && !name.endsWith('.sample');
  });

  if (!hooks.length) {
    console.log('[cp-git-hooks] 没有找到需要拷贝的 hook 文件');
    return;
  }

  for (const hook of hooks) {
    const source = join(LOCAL_HOOKS_DIR, hook);
    const target = join(targetDir, hook);

    if (existsSync(target)) {
      const sourceContent = readFileSync(source, 'utf-8');
      const targetContent = readFileSync(target, 'utf-8');

      if (sourceContent === targetContent) {
        console.log(`[cp-git-hooks] 跳过 ${hook}（内容一致）`);
        continue;
      }

      copyFileSync(source, target);
      console.log(`[cp-git-hooks] 已更新 ${hook}（内容有变更）`);
      continue;
    }

    copyFileSync(source, target);
    console.log(`[cp-git-hooks] 已拷贝 ${hook} → ${target}`);
  }
};

run();
