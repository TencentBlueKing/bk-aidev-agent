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
 * Markdown-it 自定义容器插件
 * 支持 ::: name ... ::: 语法，渲染为带 class 的 div 容器
 * name 支持字符串精确匹配和正则匹配
 *
 * 用法示例:
 *   md.use(markdownItContainer, 'warning', { ... })
 *   md.use(markdownItContainer, /^hljs-(left|center|right)$/, { ... })
 *
 * Markdown 语法:
 *   ::: hljs-left
 *   左对齐内容
 *   :::
 */

import type { MarkdownItConstructor as MarkdownIt } from '../markdown-it';
import type { Options, Renderer, StateBlock, Token } from '../markdown-it';

export type ContainerOptions = {
  marker?: string;
  render?: RenderFunction;
  validate?: ValidateFunction;
};

type RenderFunction = (tokens: Token[], idx: number, options: Options, env: unknown, slf: Renderer) => string;
type ValidateFunction = (params: string, markup: string) => boolean;

/**
 * 从 ::: 后面的文本中提取容器名称
 * 例如 " hljs-left some-extra" → "hljs-left"
 */
const extractContainerName = (params: string): string => params.trim().split(' ', 2)[0] ?? '';

export const markdownItContainer = (md: MarkdownIt, name: RegExp | string, options?: ContainerOptions): void => {
  const opts = options ?? {};
  const minMarkers = 3;
  const markerStr = opts.marker ?? ':';
  const markerChar = markerStr.charCodeAt(0);
  const markerLen = markerStr.length;

  // 生成唯一的规则标识符，用于 ruler 注册和 token type
  const ruleId = typeof name === 'string' ? name : `regex_${name.source.replace(/\W/g, '_')}`;

  const validateDefault: ValidateFunction = params => {
    const containerName = extractContainerName(params);
    return typeof name === 'string' ? containerName === name : name.test(containerName);
  };

  const renderDefault: RenderFunction = (tokens, idx, _options, _env, slf) => {
    if (tokens[idx]?.nesting === 1) {
      // 正则模式下从 info 中提取实际匹配的容器名称作为 class
      const className = typeof name === 'string' ? name : extractContainerName(tokens[idx]?.info ?? '');
      tokens[idx]!.attrJoin('class', className);
    }
    return slf.renderToken(tokens, idx, _options);
  };

  const validate = opts.validate ?? validateDefault;
  const render = opts.render ?? renderDefault;

  /**
   * 块级规则：解析 ::: name ... ::: 容器语法
   */
  const container = (state: StateBlock, startLine: number, endLine: number, silent: boolean): boolean => {
    let pos: number;
    let autoClosed = false;
    let start = (state.bMarks[startLine] ?? 0) + (state.tShift[startLine] ?? 0);
    let max = state.eMarks[startLine] ?? 0;

    // 快速检查首字符是否为 marker
    if (markerChar !== state.src.charCodeAt(start)) {
      return false;
    }

    // 验证完整的 marker 序列（如 :::）
    for (pos = start + 1; pos <= max; pos++) {
      if (markerStr[(pos - start) % markerLen] !== state.src[pos]) {
        break;
      }
    }

    const markerCount = Math.floor((pos - start) / markerLen);
    if (markerCount < minMarkers) {
      return false;
    }
    // 对齐到 marker 长度的整数倍
    pos -= (pos - start) % markerLen;

    const markup = state.src.slice(start, pos);
    const params = state.src.slice(pos, max);
    if (!validate(params, markup)) {
      return false;
    }

    // silent 模式只做验证，不生成 token
    if (silent) {
      return true;
    }

    // 向下搜索闭合 marker
    let nextLine = startLine;
    for (;;) {
      nextLine++;
      if (nextLine >= endLine) {
        break;
      }

      start = (state.bMarks[nextLine] ?? 0) + (state.tShift[nextLine] ?? 0);
      max = state.eMarks[nextLine] ?? 0;

      // 负缩进的非空行终止容器（列表嵌套场景）
      if (start < max && (state.sCount[nextLine] ?? 0) < state.blkIndent) {
        break;
      }

      if (markerChar !== state.src.charCodeAt(start)) {
        continue;
      }

      // 闭合 marker 的缩进不能 >= 4 空格
      if ((state.sCount[nextLine] ?? 0) - state.blkIndent >= 4) {
        continue;
      }

      for (pos = start + 1; pos <= max; pos++) {
        if (markerStr[(pos - start) % markerLen] !== state.src[pos]) {
          break;
        }
      }

      // 闭合 marker 长度必须 >= 开头 marker
      if (Math.floor((pos - start) / markerLen) < markerCount) {
        continue;
      }

      // 闭合行 marker 后只允许空白
      pos -= (pos - start) % markerLen;
      pos = state.skipSpaces(pos);
      if (pos < max) {
        continue;
      }

      autoClosed = true;
      break;
    }

    const oldParent = state.parentType;
    const oldLineMax = state.lineMax;
    // markdown-it 内部类型定义未包含 'container'，但运行时支持
    (state as unknown as Record<string, unknown>).parentType = 'container';
    state.lineMax = nextLine;

    const openToken = state.push(`container_${ruleId}_open`, 'div', 1);
    openToken.markup = markup;
    openToken.block = true;
    openToken.info = params;
    openToken.map = [startLine, nextLine];
    const className = typeof name === 'string' ? name : extractContainerName(params ?? '');
    openToken.attrJoin('class', className);

    // 递归解析容器内部内容
    state.md.block.tokenize(state, startLine + 1, nextLine);

    const closeToken = state.push(`container_${ruleId}_close`, 'div', -1);
    closeToken.markup = state.src.slice(start, pos);
    closeToken.block = true;

    state.parentType = oldParent;
    state.lineMax = oldLineMax;
    state.line = nextLine + (autoClosed ? 1 : 0);

    return true;
  };

  md.block.ruler.before('fence', `container_${ruleId}`, container, {
    alt: ['paragraph', 'reference', 'blockquote', 'list'],
  });
  md.renderer.rules[`container_${ruleId}_open`] = render;
  md.renderer.rules[`container_${ruleId}_close`] = render;
};

export default markdownItContainer;
