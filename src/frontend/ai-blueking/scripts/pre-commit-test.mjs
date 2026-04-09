#!/usr/bin/env node
/**
 * Pre-commit 测试脚本
 * 检测 packages/chat-x/src 目录的改动：
 * 1. 检查对应的单元测试是否已更新
 * 2. 检查对应的 Wiki 文档是否已更新
 * 3. 运行相关的单元测试
 */

import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { basename, dirname, extname, join } from 'node:path';

const SRC_PATH = 'packages/chat-x/src';
const WIKI_PATH = 'packages/chat-x/wikis';
const TEST_SUFFIX = '.spec.ts';

// 原子组件目录（对应 wikis/components/atomic/）
const ATOMIC_COMPONENT_DIRS = ['ai-buttons', 'ai-shortcut', 'markdown-token'];
// 分子组件目录（对应 wikis/components/molecular/）
const MOLECULAR_COMPONENT_DIRS = [
  'chat-input',
  'chat-message',
  'chat-content',
  'tool-call',
  'message-tools',
  'ai-selection',
];

/**
 * 检查文件是否也在 staged 中
 */
const checkFilesUpdated = (filesMap, stagedFiles, fileKey = 'file') => {
  const stagedSet = new Set(stagedFiles);
  const notUpdated = [];

  for (const item of filesMap) {
    const file = item[fileKey];
    if (file && !stagedSet.has(file)) {
      notUpdated.push(item);
    }
  }

  return notUpdated;
};

/**
 * 根据源文件找到对应的 Wiki 文档
 * @returns {{ wikiFile: string, srcFile: string }[]}
 */
const findWikiFiles = srcFiles => {
  const wikiFilesMap = [];

  for (const srcFile of srcFiles) {
    // 解析路径
    const relativePath = srcFile.replace(`${SRC_PATH}/`, '');
    const parts = relativePath.split('/');

    let wikiFile = null;

    // 组件文档
    if (parts[0] === 'components' && parts.length >= 3) {
      const componentCategory = parts[1]; // 如 ai-shortcut, chat-input
      const componentName = parts[2]; // 如 shortcut-btn

      // 判断是原子组件还是分子组件
      if (ATOMIC_COMPONENT_DIRS.includes(componentCategory)) {
        wikiFile = join(WIKI_PATH, 'components', 'atomic', `${componentName}.md`);
      } else if (MOLECULAR_COMPONENT_DIRS.includes(componentCategory)) {
        wikiFile = join(WIKI_PATH, 'components', 'molecular', `${componentName}.md`);
      }
    }
    // Composables 文档
    else if (parts[0] === 'composables' && parts.length >= 2) {
      const fileName = basename(parts[1], extname(parts[1]));
      wikiFile = join(WIKI_PATH, 'composables', `${fileName}.md`);
    }
    // 指令文档
    else if (parts[0] === 'directives' && parts.length >= 2) {
      const fileName = basename(parts[1], extname(parts[1]));
      wikiFile = join(WIKI_PATH, 'directives', `${fileName}.md`);
    }
    // 插件文档
    else if (parts[0] === 'plugins' && parts.length >= 2) {
      const fileName = basename(parts[1], extname(parts[1]));
      wikiFile = join(WIKI_PATH, 'plugins', `${fileName}.md`);
    }

    // 检查 Wiki 文件是否存在
    if (wikiFile && existsSync(wikiFile)) {
      // 避免重复
      if (!wikiFilesMap.some(item => item.wikiFile === wikiFile)) {
        wikiFilesMap.push({ wikiFile, srcFile });
      }
    }
  }

  return wikiFilesMap;
};

/**
 * 过滤出 packages/chat-x/src 目录下的源文件
 */
const filterSrcFiles = files => {
  return files.filter(file => {
    // 只关注 src 目录下的 .vue 和 .ts 文件（排除测试文件和类型定义）
    if (!file.startsWith(SRC_PATH)) return false;
    if (file.endsWith(TEST_SUFFIX)) return false;
    if (file.endsWith('.d.ts')) return false;
    return file.endsWith('.vue') || file.endsWith('.ts');
  });
};

/**
 * 根据源文件找到对应的测试文件
 * @returns {{ testFile: string, srcFile: string }[]}
 */
const findTestFiles = srcFiles => {
  const testFilesMap = [];

  for (const srcFile of srcFiles) {
    const dir = dirname(srcFile);
    const ext = extname(srcFile);
    const name = basename(srcFile, ext);

    // 尝试多种测试文件命名方式
    const possibleTestFiles = [
      // 同目录下的 xxx.spec.ts
      join(dir, `${name}${TEST_SUFFIX}`),
    ];

    // 如果源文件在子目录中（如 shortcut-btn/shortcut-btn.vue）
    // 测试文件可能在同一目录
    const dirName = basename(dir);
    possibleTestFiles.push(join(dir, `${dirName}${TEST_SUFFIX}`));

    for (const testFile of possibleTestFiles) {
      if (existsSync(testFile)) {
        // 避免重复
        if (!testFilesMap.some(item => item.testFile === testFile)) {
          testFilesMap.push({ testFile, srcFile });
        }
        break;
      }
    }
  }

  return testFilesMap;
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
 * 主函数
 */
const main = () => {
  console.log('\n🔍 检查 packages/chat-x/src 目录的改动...\n');

  // 1. 获取 staged 文件
  const stagedFiles = getStagedFiles();
  if (stagedFiles.length === 0) {
    console.log('✅ 没有 staged 的文件');
    process.exit(0);
  }

  // 2. 过滤出 src 目录下的源文件
  const srcFiles = filterSrcFiles(stagedFiles);
  if (srcFiles.length === 0) {
    console.log('✅ packages/chat-x/src 目录没有改动，跳过检查');
    process.exit(0);
  }

  console.log('📝 发现以下源文件改动：');
  srcFiles.forEach(file => console.log(`   - ${file}`));

  let hasBlockingIssue = false;

  // 3. 找到对应的测试文件
  const testFilesMap = findTestFiles(srcFiles);

  if (testFilesMap.length === 0) {
    console.log('\n⚠️  源文件改动但没有找到对应的测试文件');
    console.log('💡 提示：可以使用 @update-test 命令让 AI 帮助创建测试\n');
  } else {
    // 4. 检查测试文件是否也被更新了
    const notUpdatedTests = checkFilesUpdated(testFilesMap, stagedFiles, 'testFile');

    if (notUpdatedTests.length > 0) {
      showTestNotUpdatedWarning(notUpdatedTests);
      hasBlockingIssue = true;
    }
    // 如果测试文件已同步更新，静默通过，无需提示
  }

  // 5. 找到对应的 Wiki 文档
  const wikiFilesMap = findWikiFiles(srcFiles);

  if (wikiFilesMap.length > 0) {
    // 6. 检查 Wiki 文档是否也被更新了
    const notUpdatedWikis = checkFilesUpdated(wikiFilesMap, stagedFiles, 'wikiFile');

    if (notUpdatedWikis.length > 0) {
      showWikiNotUpdatedWarning(notUpdatedWikis);
      hasBlockingIssue = true;
    } else {
      console.log('✅ Wiki 文档已同步更新');
    }
  }

  // 如果有阻塞问题，退出
  if (hasBlockingIssue) {
    console.log('\n❌ 提交被阻止：请先更新测试用例和/或 Wiki 文档\n');
    process.exit(1);
  }

  // 7. 运行测试
  if (testFilesMap.length > 0) {
    const success = runTests(testFilesMap);
    process.exit(success ? 0 : 1);
  }

  process.exit(0);
};

/**
 * 运行测试
 */
const runTests = testFilesMap => {
  if (testFilesMap.length === 0) {
    console.log('✅ 没有找到需要运行的测试文件');
    return true;
  }

  const testFiles = testFilesMap.map(item => item.testFile);

  console.log('\n📋 将运行以下测试文件：');
  testFiles.forEach(file => console.log(`   - ${file}`));
  console.log('');

  try {
    // 使用 vitest run 运行指定的测试文件
    // 将路径转换为相对于 packages/chat-x 的路径，因为 vitest 在该目录下运行
    const relativeTestPaths = testFiles.map(file => file.replace('packages/chat-x/', '')).join(' ');
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
 * 显示测试未更新的警告
 */
const showTestNotUpdatedWarning = notUpdatedFiles => {
  console.log('\n⚠️  检测到以下源文件改动，但对应的测试文件未更新：\n');

  for (const { srcFile, testFile } of notUpdatedFiles) {
    console.log(`   源文件: ${srcFile}`);
    console.log(`   测试文件: ${testFile}`);
    console.log('');
  }

  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
  console.log('  💡 请使用 Cursor 的 update-test 命令来更新测试用例：');
  console.log('');
  console.log('     1. 在 Cursor 中按 Cmd+Shift+P (Mac) 或 Ctrl+Shift+P (Windows)');
  console.log('     2. 输入 "update-test" 并选择该命令');
  console.log('     3. AI 将自动分析改动并更新测试用例');
  console.log('');
  console.log('  或者直接在 Cursor 聊天中输入：');
  console.log('     @update-test');
  console.log('');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
};

/**
 * 显示 Wiki 未更新的警告
 */
const showWikiNotUpdatedWarning = notUpdatedFiles => {
  console.log('\n⚠️  检测到以下源文件改动，但对应的 Wiki 文档未更新：\n');

  for (const { srcFile, wikiFile } of notUpdatedFiles) {
    console.log(`   源文件: ${srcFile}`);
    console.log(`   Wiki 文档: ${wikiFile}`);
    console.log('');
  }

  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
  console.log('  💡 请使用 Cursor 的 update-wiki 命令来更新 Wiki 文档：');
  console.log('');
  console.log('     1. 在 Cursor 中按 Cmd+Shift+P (Mac) 或 Ctrl+Shift+P (Windows)');
  console.log('     2. 输入 "update-wiki" 并选择该命令');
  console.log('     3. AI 将自动分析改动并更新 Wiki 文档');
  console.log('');
  console.log('  或者直接在 Cursor 聊天中输入：');
  console.log('     @update-wiki');
  console.log('');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
};

main();
