/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/**
 * Markdown 流式渲染语法补全器
 * 用于在流式输入过程中补全不完整的 markdown 语法，提升渲染效果
 *
 * 基于行切分的高效处理策略：
 * - 跨行语法（代码块、块级公式、\begin环境）：从后向前逐行扫描
 * - 行内语法（行内代码、行内公式、链接）：只检查最后一行
 */

export interface MarkdownCompleteOptions {
  /**
   * 是否进行全量检查
   * - true: 检查整个内容的所有语法
   * - false: 只检查最后部分（性能更好，默认）
   * @default false
   */
  fullCheck?: boolean;
}

export interface MarkdownCompleteResult {
  /** 补全后的内容 */
  content: string;
  /** 补全添加的后缀（用于后续流式输入完整时去掉） */
  suffix: string;
}

// ============================================================================
// 正则表达式常量 (预编译以提升性能)
// ============================================================================
const REGEX_CODE_BLOCK = /^```/;
const REGEX_DOUBLE_DOLLAR = /\$\$/g;
const REGEX_BRACKET_OPEN = /\\\[/g;
const REGEX_BRACKET_CLOSE = /\\\]/g;
const REGEX_BEGIN_ENV = /\\begin\{([^}]+)\}/g;
const REGEX_END_ENV = /\\end\{([^}]+)\}/g;
const REGEX_INCOMPLETE_BEGIN = /\\begin\{([^}]*)$/;
const REGEX_INCOMPLETE_END = /\\end\{([^}]*)$/;
const REGEX_INCOMPLETE_CMD = /\\([a-zA-Z]+)$/;
// const REGEX_INLINE_CODE = /`/g;
// const REGEX_SINGLE_DOLLAR = /\$/g; // 注意：通常需要排除转义

// LaTeX 命令列表
const TWO_ARG_COMMANDS = new Set([
  'frac',
  'dfrac',
  'tfrac',
  'binom',
  'dbinom',
  'tbinom',
  'cfrac',
  'overset',
  'underset',
]);
const ONE_ARG_COMMANDS = new Set([
  'sqrt',
  'text',
  'mathbf',
  'mathit',
  'mathrm',
  'mathcal',
  'mathbb',
  'hat',
  'bar',
  'vec',
  'dot',
  'ddot',
  'tilde',
  'widehat',
  'widetilde',
  'overline',
  'underline',
]);

const COMMON_ENVS = [
  'aligned',
  'align',
  'equation',
  'gather',
  'matrix',
  'pmatrix',
  'bmatrix',
  'vmatrix',
  'Bmatrix',
  'Vmatrix',
  'cases',
  'array',
  'split',
  'multline',
];

/**
 * 主补全函数
 * 基于行切分，按优先级检查需要补全的语法
 */
export function completeMarkdownSyntax(content: string, options: MarkdownCompleteOptions = {}): MarkdownCompleteResult {
  if (!content) {
    return { content: '', suffix: '' };
  }

  const { fullCheck = false } = options;

  // 按行切分
  const lines = content.split('\n');

  let suffix = '';

  // ============================================================================
  // 1. 跨行语法检查（从后向前扫描）
  // ============================================================================

  // 1.1 代码块检查（最高优先级，在代码块内不检查其他语法）
  const codeBlockResult = checkCodeBlock(lines);
  if (codeBlockResult.inCodeBlock) {
    return {
      content: `${content}\n\`\`\``,
      suffix: '\n```',
    };
  }

  // 1.2 \[...\] 块级公式检查
  const bracketBlockResult = checkBracketBlock(lines, fullCheck);
  if (bracketBlockResult) {
    suffix += bracketBlockResult;
  }

  // 1.3 $$...$$ 块级公式检查
  const doubleDollarResult = checkDoubleDollar(lines, fullCheck);
  if (doubleDollarResult) {
    suffix += doubleDollarResult;
  }

  // 1.4 \begin{env} 环境检查（包括不完整的 \begin{ 语法）
  // 放在 $$ 检查之后，因为如果在 $$ 内部，\begin 不需要额外的补全（通常由 Latex 渲染器处理）
  // 但这里为了保险起见，还是做检查，因为 markdown-it-latex 可能依赖显式的闭合
  const beginEndResult = checkBeginEnd(lines, fullCheck);
  if (beginEndResult) {
    suffix += beginEndResult;
  }

  // 1.5 检查是否在 LaTeX 块级公式内
  // 优化：直接使用前面的检查结果，避免 checkInLatexBlock 的重复全量扫描
  const inLatexBlock = !!bracketBlockResult || !!doubleDollarResult;

  // 1.6 如果在 LaTeX 块中，检查不完整的 LaTeX 语法
  if (inLatexBlock) {
    const latexSyntaxResult = checkIncompleteLatexSyntax(content);
    if (latexSyntaxResult) {
      // 将 LaTeX 语法补全插入到块级闭合符号之前
      suffix = latexSyntaxResult + suffix;
    }
  }

  // ============================================================================
  // 2. 行内语法检查（只检查最后一行）
  // ============================================================================

  const lastLine = lines[lines.length - 1] || '';

  // 2.1 行内代码检查
  const inlineCodeResult = checkInlineCode(lastLine);
  if (inlineCodeResult) {
    suffix += inlineCodeResult;
  }

  // 2.2 \(...\) 行内公式检查
  const parenResult = checkParen(lastLine);
  if (parenResult) {
    suffix += parenResult;
  }

  // 2.3 $...$ 行内公式检查（如果已经补全了 $$，跳过）
  if (!doubleDollarResult) {
    const singleDollarResult = checkSingleDollar(lastLine);
    if (singleDollarResult) {
      suffix += singleDollarResult;
    }
  }

  // 2.4 链接/图片检查
  const linkResult = checkLink(lastLine);
  if (linkResult) {
    suffix += linkResult;
  }

  return {
    content: content + suffix,
    suffix,
  };
}

/**
 * 检查内容是否需要补全
 * 轻量级检查，用于快速判断是否需要调用完整的补全函数
 */
export function needsMarkdownCompletion(content: string): boolean {
  if (!content) {
    return false;
  }

  // 快速检查是否包含可能需要补全的字符
  const potentialMarkers = ['`', '[', '$', '\\'];
  for (const marker of potentialMarkers) {
    if (content.includes(marker)) return true;
  }
  return false;
}

/**
 * 从补全内容中移除之前添加的后缀
 */
export function removeCompletionSuffix(content: string, previousSuffix: string): string {
  if (!previousSuffix || !content.endsWith(previousSuffix)) {
    return content;
  }
  return content.slice(0, -previousSuffix.length);
}

/**
 * 检查 \begin{env}...\end{env} 环境
 */
function checkBeginEnd(lines: string[], fullCheck: boolean): string {
  const content = lines.join('\n');

  // 1. 检查不完整的命令结尾
  if (/[^\\]\\(e|en|end)$/.test(content)) return ''; // 正在输入 \end
  if (/[^\\]\\(b|be|beg|begi|begin)$/.test(content)) return ''; // 正在输入 \begin

  // 2. 检查不完整的 \end{...
  const incompleteEndMatch = content.match(REGEX_INCOMPLETE_END);
  if (incompleteEndMatch) {
    const partialEnv = incompleteEndMatch[1] || '';
    const guessedEnv = guessEnvironmentName(partialEnv);
    if (guessedEnv) {
      return `${guessedEnv.slice(partialEnv.length)}}`;
    }
    return '}';
  }

  // 3. 检查不完整的 \begin{...
  const incompleteBeginMatch = content.match(REGEX_INCOMPLETE_BEGIN);
  if (incompleteBeginMatch) {
    const partialEnv = incompleteBeginMatch[1] || '';
    const guessedEnv = guessEnvironmentName(partialEnv);
    if (guessedEnv) {
      return `${guessedEnv.slice(partialEnv.length)}}\\end{${guessedEnv}}`;
    }
    return '}';
  }

  // 4. 处理完整的 \begin{env} 和 \end{env} 配对
  const envStack: string[] = [];
  const startIndex = fullCheck ? 0 : Math.max(0, lines.length - 50);

  for (let i = startIndex; i < lines.length; i++) {
    const line = lines[i] || '';

    // 重置正则 LastIndex
    REGEX_BEGIN_ENV.lastIndex = 0;
    REGEX_END_ENV.lastIndex = 0;

    // 查找所有完整的 \begin{env}
    let match;

    while ((match = REGEX_BEGIN_ENV.exec(line)) !== null) {
      if (match[1]) envStack.push(match[1]);
    }

    // 查找所有完整的 \end{env}

    while ((match = REGEX_END_ENV.exec(line)) !== null) {
      if (match[1]) {
        const idx = envStack.lastIndexOf(match[1]);
        if (idx !== -1) {
          envStack.splice(idx, 1);
        }
      }
    }
  }

  if (envStack.length > 0) {
    const lastEnv = envStack[envStack.length - 1];
    return `\n\\end{${lastEnv}}`;
  }

  return '';
}

// ============================================================================
// 跨行语法检查函数
// ============================================================================

/**
 * 检查 \[...\] 块级公式
 */
function checkBracketBlock(lines: string[], fullCheck: boolean): string {
  let openCount = 0;
  const startIndex = fullCheck ? 0 : Math.max(0, lines.length - 30);

  for (let i = startIndex; i < lines.length; i++) {
    const line = lines[i] || '';
    openCount += countMatches(line, REGEX_BRACKET_OPEN);
    openCount -= countMatches(line, REGEX_BRACKET_CLOSE);
  }

  if (openCount > 0) {
    return '\n\\]';
  }

  return '';
}

/**
 * 检查代码块是否闭合
 */
function checkCodeBlock(lines: string[]): { inCodeBlock: boolean } {
  let inCodeBlock = false;
  for (const line of lines) {
    if (REGEX_CODE_BLOCK.test(line.trim())) {
      inCodeBlock = !inCodeBlock;
    }
  }
  return { inCodeBlock };
}

/**
 * 检查 $$...$$ 块级公式
 */
function checkDoubleDollar(lines: string[], fullCheck: boolean): string {
  let count = 0;
  const startIndex = fullCheck ? 0 : Math.max(0, lines.length - 30);

  for (let i = startIndex; i < lines.length; i++) {
    const line = lines[i] || '';
    count += countMatches(line, REGEX_DOUBLE_DOLLAR);
  }

  if (count % 2 === 1) {
    const lastLine = lines[lines.length - 1] || '';
    const trimmedLastLine = lastLine.trimEnd();

    // 如果最后一行以单个 $ 结尾（不是 $$），说明用户正在输入 $$，只需补全一个 $
    if (trimmedLastLine.endsWith('$') && !trimmedLastLine.endsWith('$$')) {
      return '$';
    }
    return '\n$$';
  }

  return '';
}

/**
 * 检查不完整的 LaTeX 语法
 */
function checkIncompleteLatexSyntax(content: string): string {
  let suffix = '';

  if (/\\(begin|end)\{[^}]*$/.test(content)) {
    return '';
  }

  const incompleteCommandMatch = content.match(REGEX_INCOMPLETE_CMD);
  const cmd = incompleteCommandMatch?.[1];
  if (cmd) {
    if (TWO_ARG_COMMANDS.has(cmd)) {
      suffix += '{}{}';
    } else if (ONE_ARG_COMMANDS.has(cmd)) {
      suffix += '{}';
    }
  }

  const contentWithoutEnvs = content.replace(/\\(begin|end)\{[^}]*\}?/g, '');
  let braceCount = 0;
  for (const char of contentWithoutEnvs) {
    if (char === '{') braceCount++;
    else if (char === '}') braceCount--;
  }
  if (braceCount > 0) {
    suffix += '}'.repeat(braceCount);
  }

  return suffix;
}

/**
 * 检查行内代码
 */
function checkInlineCode(line: string): string {
  let count = 0;
  // 手动遍历以处理转义
  for (let i = 0; i < line.length; i++) {
    if (line[i] === '`') {
      if (i === 0 || line[i - 1] !== '\\') {
        count++;
      }
    }
  }

  if (count % 2 === 1) {
    return '`';
  }
  return '';
}

/**
 * 检查链接语法
 */
function checkLink(line: string): string {
  const lastOpenBracket = line.lastIndexOf('[');
  if (lastOpenBracket === -1) return '';

  if (lastOpenBracket > 0 && line[lastOpenBracket - 1] === '!') return '';

  const afterOpen = line.slice(lastOpenBracket);
  if (/^\[[^\]]*\]\([^)]*\)/.test(afterOpen)) return ''; // 已闭合

  if (!afterOpen.includes(']')) {
    return '](​)'; // 使用零宽字符防止空链接折叠，或根据需求调整
  }

  const closeBracketPos = afterOpen.indexOf(']');
  const afterClose = afterOpen.slice(closeBracketPos + 1);
  if (afterClose.startsWith('(') && !afterClose.includes(')')) {
    return ')';
  }

  return '';
}

/**
 * 检查 \(...\) 行内公式
 */
function checkParen(line: string): string {
  const openCount = countMatches(line, /\\\(/g);
  const closeCount = countMatches(line, /\\\)/g);

  if (openCount > closeCount) {
    return '\\)';
  }
  return '';
}

/**
 * 检查 $...$ 行内公式
 */
function checkSingleDollar(line: string): string {
  // 先移除 $$
  const lineWithoutDoubleDollar = line.replace(REGEX_DOUBLE_DOLLAR, '');

  // 简化的检查，手动循环处理转义更准确，但正则替换掉 \$$ 后直接 count 也行
  // 这里保持原有的精确逻辑
  let count = 0;
  for (let i = 0; i < lineWithoutDoubleDollar.length; i++) {
    if (lineWithoutDoubleDollar[i] === '$') {
      if (i === 0 || lineWithoutDoubleDollar[i - 1] !== '\\') {
        count++;
      }
    }
  }

  if (count % 2 === 1) {
    return '$';
  }
  return '';
}

/**
 * 辅助函数：计算字符串中正则匹配的次数 (避免创建临时数组)
 */
function countMatches(str: string, regex: RegExp): number {
  let count = 0;
  regex.lastIndex = 0; // 重置正则状态
  while (regex.test(str)) {
    count++;
  }
  return count;
}

function guessEnvironmentName(partial: string): string {
  for (const env of COMMON_ENVS) {
    if (env.startsWith(partial)) {
      return env;
    }
  }
  return '';
}
