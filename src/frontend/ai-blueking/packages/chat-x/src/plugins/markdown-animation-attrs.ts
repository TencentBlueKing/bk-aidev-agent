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

import type MarkdownIt from 'markdown-it/index.js';

/**
 * 添加 markdown 动画属性
 * @param md - markdown-it 实例
 */
export const markdownAnimationAttrs = (md: MarkdownIt) => {
  md.core.ruler.push('markdown-animation-attrs', state => {
    const { tokens } = state;
    for (const token of tokens) {
      if (!token.attrs) {
        token.attrs = [];
      }
      if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(token.tag) && token.nesting === 1) {
        token.attrs.push(['class', 'ai-blueking-typewriter']);
        continue;
      }
      if (token.block && token.nesting === 1 && !['ul', 'ol'].includes(token.tag)) {
        token.attrs.push(['class', 'ai-blueking-markdown-fade-in']);
      }
    }
  });
};
