import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/**
 * 计算下一个版本号。
 * @param {string} current 当前 package.json 版本
 * @param {string} [explicit] 显式版本，非空时原样返回
 */
export function computeNextVersion(current, explicit) {
  if (explicit) return explicit;
  const m = current.match(/^(\d+\.\d+\.\d+-(?:alpha|beta|rc)\.)(\d+)$/);
  if (!m) {
    throw new Error(`当前版本 ${current} 是正式版，正式版必须显式指定版本号发布`);
  }
  return `${m[1]}${Number(m[2]) + 1}`;
}

/**
 * 解析 npm dist-tag。
 * @param {string} version 版本号，如 2.1.0-beta.4
 * @param {string} [override] 显式覆盖，非空时优先返回
 */
export function resolveTag(version, override) {
  if (override) return override;
  if (/-alpha\./.test(version)) return 'alpha';
  if (/-beta\./.test(version)) return 'beta';
  if (/-rc\./.test(version)) return 'rc';
  return 'latest';
}

function main() {
  const [dir, explicitArg = '', tagArg = ''] = process.argv.slice(2);
  if (!dir) {
    console.error('usage: node bump-version.mjs <package-dir> [version] [tag]');
    process.exit(1);
  }
  const pkgPath = `${dir}/package.json`;
  const current = JSON.parse(readFileSync(pkgPath, 'utf8')).version;
  const next = computeNextVersion(current, explicitArg || undefined);
  // 用 npm version 写回 package.json，保持与旧逻辑一致的行为与格式
  execFileSync('npm', ['version', next, '--no-git-tag-version'], {
    cwd: dir,
    stdio: ['ignore', 'ignore', 'inherit'], // npm 自身输出不污染 stdout（stdout 会被重定向到 $GITHUB_OUTPUT）
  });
  const tag = resolveTag(next, tagArg || undefined);
  console.error(`[bump] ${dir}: ${current} -> ${next} (tag: ${tag})`); // 日志走 stderr
  process.stdout.write(`version=${next}\n`);
  process.stdout.write(`npm_tag=${tag}\n`);
}

// 仅在被直接执行时跑 CLI；被 import 时只导出纯函数
if (process.argv[1] === fileURLToPath(import.meta.url)) main();
