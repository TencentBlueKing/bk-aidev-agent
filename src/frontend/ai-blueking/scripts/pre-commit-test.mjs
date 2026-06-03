#!/usr/bin/env node
/**
 * Pre-commit 测试脚本
 * 检测 packages/chat-x/src 目录的改动：
 * 1. 检查对应的单元测试是否已更新
 * 2. 检查对应的 Wiki 文档是否已更新
 * 3. 运行相关的单元测试
 */

import { execSync } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import { basename, dirname, extname, join, relative } from 'node:path';

// git root 与当前 workspace 可能不在同一层（monorepo 场景）
const GIT_ROOT = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim();
const WORKSPACE_ROOT = join(import.meta.dirname, '..');
const MONOREPO_PREFIX = relative(GIT_ROOT, WORKSPACE_ROOT);

const CHAT_X_PATH = join(MONOREPO_PREFIX, 'packages/chat-x');
const SRC_PATH = join(CHAT_X_PATH, 'src');
const WIKI_PATH = join(CHAT_X_PATH, 'wikis');
const TEST_SUFFIX = '.spec.ts';

/** 源码文件名与文档 slug 不一致的组件 */
const COMPONENT_DOC_NAME_OVERRIDES = {
  'components/image-preview/image.vue': 'ai-image',
};

const getComponentWikiSubdirs = () => {
  const componentsWikiPath = join(WIKI_PATH, 'components');
  if (!existsSync(componentsWikiPath)) return [];
  return readdirSync(componentsWikiPath, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name);
};

/**
 * 过滤出 packages/chat-x/src 目录下的源文件（.vue / .ts，排除测试和类型定义）
 */
const filterSrcFiles = files => {
  return files.filter(
    file =>
      file.startsWith(SRC_PATH) &&
      !file.endsWith(TEST_SUFFIX) &&
      !file.endsWith('.d.ts') &&
      (file.endsWith('.vue') || file.endsWith('.ts')),
  );
};

/**
 * 在 stagedSet 中检查 targetFiles 是否已被暂存
 * @returns 未暂存的文件列表 { target, src }[]
 */
const findUnstaged = (targetFiles, stagedSet) => {
  return targetFiles.filter(({ target }) => !stagedSet.has(target));
};

/**
 * 根据源文件找到对应的测试文件
 * @returns {{ target: string, src: string }[]}
 */
const findTestFiles = srcFiles => {
  const seen = new Set();
  const result = [];

  for (const srcFile of srcFiles) {
    const dir = dirname(srcFile);
    const name = basename(srcFile, extname(srcFile));
    const dirName = basename(dir);

    const candidates = [join(dir, `${name}${TEST_SUFFIX}`)];
    // 避免 name === dirName 时产生重复候选路径
    if (name !== dirName) {
      candidates.push(join(dir, `${dirName}${TEST_SUFFIX}`));
    }

    for (const testFile of candidates) {
      if (!seen.has(testFile) && existsSync(testFile)) {
        seen.add(testFile);
        result.push({ target: testFile, src: srcFile });
        break;
      }
    }
  }

  return result;
};

/**
 * 根据源文件找到对应的 Wiki 文档
 * @returns {{ target: string, src: string }[]}
 */
const findWikiFiles = srcFiles => {
  const seen = new Set();
  const result = [];

  for (const srcFile of srcFiles) {
    const relativePath = srcFile.replace(`${SRC_PATH}/`, '');
    const parts = relativePath.split('/');
    const topDir = parts[0];

    let wikiFile = null;

    if (topDir === 'components' && parts.length >= 3) {
      // 组件文档按能力域目录组织，按源码文件名对应的 slug 查找
      const override = COMPONENT_DOC_NAME_OVERRIDES[relativePath];
      const docSlug = override ?? basename(parts.at(-1), extname(parts.at(-1)));
      const docName = `${docSlug}.md`;
      wikiFile = getComponentWikiSubdirs()
        .map(sub => join(WIKI_PATH, 'components', sub, docName))
        .find(p => existsSync(p));
    } else if (parts.length >= 2) {
      // composables / directives / plugins 等直接按 topDir 映射
      const fileName = basename(parts[1], extname(parts[1]));
      const candidate = join(WIKI_PATH, topDir, `${fileName}.md`);
      if (existsSync(candidate)) wikiFile = candidate;
    }

    if (wikiFile && !seen.has(wikiFile)) {
      seen.add(wikiFile);
      result.push({ target: wikiFile, src: srcFile });
    }
  }

  return result;
};

/**
 * 获取 staged 的文件列表
 */
const getStagedFiles = () => {
  try {
    const output = execSync('git diff --cached --name-only --diff-filter=ACMR', {
      encoding: 'utf-8',
    });
    return output.trim().split('\n').filter(Boolean);
  } catch {
    return [];
  }
};

/**
 * 运行测试
 */
const runTests = testFiles => {
  console.log('\n📋 将运行以下测试文件：');
  for (const file of testFiles) console.log(`   - ${file}`);
  console.log('');

  try {
    const relativeTestPaths = testFiles.map(f => f.replace(`${CHAT_X_PATH}/`, '')).join(' ');
    execSync(`pnpm --filter @blueking/chat-x exec vitest run ${relativeTestPaths}`, {
      stdio: 'inherit',
      cwd: process.cwd(),
    });
    console.log('\n✅ 所有测试通过！\n');
    return true;
  } catch {
    console.error('\n❌ 测试失败！请修复测试后再提交。\n');
    console.log('💡 提示：可以使用 @update-test 命令让 AI 帮助修复测试\n');
    return false;
  }
};

/**
 * 显示文件未更新的警告
 * @param {'test' | 'wiki'} type 检查类型
 * @param {{ target: string, src: string }[]} items 未更新的文件列表
 */
const showNotUpdatedWarning = (type, items) => {
  const isTest = type === 'test';
  const label = isTest ? '测试文件' : 'Wiki 文档';
  const command = isTest ? 'update-test' : 'update-wiki';

  console.log(`\n⚠️  检测到以下源文件改动，但对应的${label}未更新：\n`);

  for (const { src, target } of items) {
    console.log(`   源文件: ${src}`);
    console.log(`   ${label}: ${target}`);
    console.log('');
  }

  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
  console.log(`  💡 请使用 Cursor 的 ${command} 命令来更新${label}：`);
  console.log('');
  console.log('     1. 在 Cursor 中按 Cmd+Shift+P (Mac) 或 Ctrl+Shift+P (Windows)');
  console.log(`     2. 输入 "${command}" 并选择该命令`);
  console.log(`     3. AI 将自动分析改动并更新${label}`);
  console.log('');
  console.log('  或者直接在 Cursor 聊天中输入：');
  console.log(`     @${command}`);
  console.log('');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
};

/**
 * 主函数
 */
const main = () => {
  console.log('\n🔍 检查 packages/chat-x/src 目录的改动...\n');

  const stagedFiles = getStagedFiles();
  if (stagedFiles.length === 0) {
    console.log('✅ 没有 staged 的文件');
    process.exit(0);
  }

  const srcFiles = filterSrcFiles(stagedFiles);
  if (srcFiles.length === 0) {
    console.log('✅ packages/chat-x/src 目录没有改动，跳过检查');
    process.exit(0);
  }

  console.log('📝 发现以下源文件改动：');
  for (const file of srcFiles) console.log(`   - ${file}`);

  const stagedSet = new Set(stagedFiles);
  let hasBlockingIssue = false;

  // 检查测试文件
  const testFilesMap = findTestFiles(srcFiles);

  if (testFilesMap.length === 0) {
    console.log('\n⚠️  源文件改动但没有找到对应的测试文件');
    console.log('💡 提示：可以使用 @update-test 命令让 AI 帮助创建测试\n');
  } else {
    const notUpdatedTests = findUnstaged(testFilesMap, stagedSet);
    if (notUpdatedTests.length > 0) {
      showNotUpdatedWarning('test', notUpdatedTests);
      hasBlockingIssue = true;
    }
  }

  // 检查 Wiki 文档
  const wikiFilesMap = findWikiFiles(srcFiles);

  if (wikiFilesMap.length > 0) {
    const notUpdatedWikis = findUnstaged(wikiFilesMap, stagedSet);
    if (notUpdatedWikis.length > 0) {
      showNotUpdatedWarning('wiki', notUpdatedWikis);
      hasBlockingIssue = true;
    } else {
      console.log('✅ Wiki 文档已同步更新');
    }
  }

  if (hasBlockingIssue) {
    console.log('\n❌ 提交被阻止：请先更新测试用例和/或 Wiki 文档\n');
    process.exit(1);
  }

  // 运行测试
  if (testFilesMap.length > 0) {
    const testFiles = testFilesMap.map(item => item.target);
    process.exit(runTests(testFiles) ? 0 : 1);
  }

  process.exit(0);
};

main();
