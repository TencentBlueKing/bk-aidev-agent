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

import type { Options, PluginSimple, Renderer, Token } from '../markdown-it';

/** fence 渲染规则类型 */
type FenceRenderRule = NonNullable<Renderer['rules']['fence']>;

/**
 * 检查是否为 mermaid 代码块
 * @param info - 代码块的 info 字符串
 */
const isMermaidBlock = (info: string): boolean => {
  return info === 'mermaid' || info.startsWith('mermaid ');
};

/**
 * Markdown-it plugin for Mermaid diagrams with streaming and incremental rendering
 * @param md - markdown-it 实例
 */
export const markdownItMermaid: PluginSimple = md => {
  // 保存原始的 fence 渲染器（markdown-it 初始化时会设置）
  const defaultFenceRenderer = md.renderer.rules.fence as FenceRenderRule;

  // 重写 fence renderer
  md.renderer.rules.fence = (tokens: Token[], idx: number, options: Options, env: unknown, self: Renderer): string => {
    const token = tokens[idx];
    const info = token.info ? md.utils.unescapeAll(token.info).trim() : '';
    const content = token.content ?? '';

    if (isMermaidBlock(info)) {
      const encodedCode = encodeURIComponent(content);
      return `<div class="mermaid-wrapper" data-mermaid-code="${encodedCode}" data-mermaid-idx="${idx}"></div>`;
    }

    return defaultFenceRenderer(tokens, idx, options, env, self);
  };
};

export default markdownItMermaid;
