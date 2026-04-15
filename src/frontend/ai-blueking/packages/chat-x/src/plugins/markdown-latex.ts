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
 * Markdown-it LaTeX 解析插件
 * 只负责解析 LaTeX 语法（$...$, $$...$$, \(...\), \[...\]），不负责渲染
 * KaTeX 渲染在 LatexContent 组件中完成
 */

import type { PluginWithOptions } from '../markdown-it';
import type StateBlock from 'markdown-it/lib/rules_block/state_block.mjs';
import type StateInline from 'markdown-it/lib/rules_inline/state_inline.mjs';

export type LatexOption = {
  /** 是否将 align* 替换为 aligned（KaTeX 不支持 align*） */
  replaceAlignStart?: boolean;
};

/**
 * 块级公式规则
 * 匹配独立行的: $$\n...\n$$, \[...\]
 */
const blockKatexRule = (state: StateBlock, startLine: number, endLine: number, silent: boolean): boolean => {
  const startPos = (state.bMarks[startLine] ?? 0) + (state.tShift[startLine] ?? 0);
  const maxPos = state.eMarks[startLine] ?? 0;

  // 检查开头是 $$ 还是 \[
  const lineText = state.src.slice(startPos, maxPos);

  let openDelim = '';
  let closeDelim = '';

  if (lineText.startsWith('$$')) {
    openDelim = '$$';
    closeDelim = '$$';
  } else if (lineText.startsWith('\\[')) {
    openDelim = '\\[';
    closeDelim = '\\]';
  } else {
    return false;
  }

  // 如果开头和结尾在同一行
  const restOfLine = lineText.slice(openDelim.length);
  const closeIdx = restOfLine.indexOf(closeDelim);
  if (closeIdx !== -1 && restOfLine.slice(closeIdx + closeDelim.length).trim() === '') {
    // 单行块级公式
    if (silent) return true;

    const content = restOfLine.slice(0, closeIdx).trim();

    const token = state.push('math_block', 'math', 0);
    token.content = content;
    token.markup = openDelim;
    token.map = [startLine, startLine + 1];
    token.block = true;

    state.line = startLine + 1;
    return true;
  }

  // 多行块级公式
  if (lineText.trim() !== openDelim) {
    return false;
  }

  // 查找结束标记
  let nextLine = startLine + 1;
  let found = false;

  while (nextLine < endLine) {
    const lineStart = (state.bMarks[nextLine] ?? 0) + (state.tShift[nextLine] ?? 0);
    const lineEnd = state.eMarks[nextLine] ?? 0;
    const line = state.src.slice(lineStart, lineEnd);

    if (line.trim() === closeDelim) {
      found = true;
      break;
    }
    nextLine++;
  }

  if (!found) return false;
  if (silent) return true;

  // 获取公式内容
  const contentStart = state.bMarks[startLine + 1] ?? 0;
  const contentEnd = state.bMarks[nextLine] ?? 0;
  const content = state.src.slice(contentStart, contentEnd).trim();

  const token = state.push('math_block', 'math', 0);
  token.content = content;
  token.markup = openDelim;
  token.map = [startLine, nextLine + 1];
  token.block = true;

  state.line = nextLine + 1;
  return true;
};

/**
 * 查找关闭分隔符，跳过转义的分隔符
 */
const findCloseDelimiter = (src: string, closeDelim: string, start: number): number => {
  let pos = start;
  while (pos < src.length) {
    const idx = src.indexOf(closeDelim, pos);
    if (idx === -1) return -1;

    // 检查是否被转义（前面有奇数个反斜杠）
    let backslashCount = 0;
    let checkPos = idx - 1;
    while (checkPos >= 0 && src.charCodeAt(checkPos) === 0x5c /* \ */) {
      backslashCount++;
      checkPos--;
    }

    // 偶数个反斜杠（包括0个）表示没有被转义
    if (backslashCount % 2 === 0) {
      return idx;
    }

    // 被转义了，继续查找
    pos = idx + 1;
  }
  return -1;
};

/**
 * 行内公式规则
 * 匹配: $...$, $$...$$, \(...\), \[...\]
 */
const inlineKatexRule = (state: StateInline, silent: boolean): boolean => {
  const src = state.src;
  const pos = state.pos;
  const max = state.posMax;

  if (pos >= max) return false;

  // 检查 $, $$, \(, \[ 开头
  const ch = src.charCodeAt(pos);
  const ch2 = pos + 1 < max ? src.charCodeAt(pos + 1) : 0;

  let openDelim = '';
  let closeDelim = '';
  let displayMode = false;

  // $$ 块级公式（内联中也支持）
  if (ch === 0x24 /* $ */ && ch2 === 0x24 /* $ */) {
    openDelim = '$$';
    closeDelim = '$$';
    displayMode = true;
  }
  // $ 行内公式（确保不是 $$）
  else if (ch === 0x24 /* $ */ && ch2 !== 0x24 /* $ */) {
    openDelim = '$';
    closeDelim = '$';
    displayMode = false;
  }
  // \( 行内公式
  else if (ch === 0x5c /* \ */ && ch2 === 0x28 /* ( */) {
    openDelim = '\\(';
    closeDelim = '\\)';
    displayMode = false;
  }
  // \[ 块级公式
  else if (ch === 0x5c /* \ */ && ch2 === 0x5b /* [ */) {
    openDelim = '\\[';
    closeDelim = '\\]';
    displayMode = true;
  } else {
    return false;
  }

  const start = pos + openDelim.length;

  // 查找关闭分隔符
  const end = findCloseDelimiter(src, closeDelim, start);
  if (end === -1) return false;

  // 确保不是空内容
  if (end === start) return false;

  const content = src.slice(start, end).trim();
  if (!content) return false;

  if (!silent) {
    const token = state.push('math_inline', 'math', 0);
    token.content = content;
    token.markup = openDelim;
    token.meta = { displayMode };
  }

  state.pos = end + closeDelim.length;
  return true;
};

// fix katex not support align*: https://github.com/KaTeX/KaTeX/issues/1007
const replaceAlign = (text: string): string => {
  return text ? text.replace(/\{align\*\}/g, '{aligned}') : text;
};

/**
 * Markdown-it LaTeX 解析插件
 * 只负责解析，不负责渲染（渲染在 LatexContent 组件中完成）
 *
 * @param md - markdown-it 实例
 * @param options - 配置选项
 */
export const markdownItLatex: PluginWithOptions<LatexOption> = (md, options): void => {
  const { replaceAlignStart = true } = options ?? {};

  // 添加行内公式规则（放在 escape 之前，确保 \( 和 \[ 不会被转义处理）
  md.inline.ruler.before('escape', 'math_inline', inlineKatexRule);

  // 添加块级公式规则
  md.block.ruler.before('fence', 'math_block', blockKatexRule, {
    alt: ['paragraph', 'reference', 'blockquote'],
  });

  // 行内公式渲染器 - 返回空字符串
  // hasLatexToken 会检测到 math_inline token，用 LatexContent 组件渲染
  md.renderer.rules.math_inline = (tokens, idx) => {
    const token = tokens[idx];
    if (!token) return '';

    // 预处理 align* -> aligned
    if (replaceAlignStart) {
      token.content = replaceAlign(token.content);
    }

    // 返回空字符串，让 LatexContent 组件处理渲染
    return '';
  };

  // 块级公式渲染器 - 返回空字符串
  // hasLatexToken 会检测到 math_block token，用 LatexContent 组件渲染
  md.renderer.rules.math_block = (tokens, idx) => {
    const token = tokens[idx];
    if (!token) return '';

    // 预处理 align* -> aligned
    if (replaceAlignStart) {
      token.content = replaceAlign(token.content);
    }

    // 返回空字符串，让 LatexContent 组件处理渲染
    return '';
  };
};

export default markdownItLatex;
