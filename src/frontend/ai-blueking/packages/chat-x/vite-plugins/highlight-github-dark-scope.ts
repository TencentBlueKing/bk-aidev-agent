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

import postcss from 'postcss';

import type { AtRule, Container, Document, Rule } from 'postcss';
import type { Plugin } from 'vite';

/** hljs 主题仅在这些容器树下生效：消息体、文件产物预览区 */
export const HIGHLIGHT_GITHUB_DARK_SCOPE_CLASSES = ['ai-message-container', 'ai-artifact-preview-host'];

const DEFAULT_SCOPES = HIGHLIGHT_GITHUB_DARK_SCOPE_CLASSES.map(name => `.${name}`);

/** 跳过 @keyframes 内的 from/to/百分比选择器，避免生成非法 CSS */
const isInsideKeyframes = (rule: Rule): boolean => {
  // 沿父链向上查找；Node#parent 在 PostCSS 8 中可为 Document（多 Root 场景），需显式类型以通过赋值
  let parent: Container | Document | undefined = rule.parent;
  while (parent) {
    if (parent.type === 'atrule' && (parent as AtRule).name === 'keyframes') {
      return true;
    }
    parent = parent.parent;
  }
  return false;
};

/**
 * 在构建时处理 `highlight.js/styles/github-dark.css`：
 * 为每条规则的选择器增加前置 scope，
 * 将主题限制在指定容器内，减少对宿主页面全局样式的污染。
 */
export const vitePluginHighlightGithubDarkScope = (options?: {
  /** 默认 `.ai-message-container` 与 `.ai-artifact-preview-host` */
  scopeSelectors?: string[];
}): Plugin => {
  const scopes = options?.scopeSelectors?.length ? options.scopeSelectors : DEFAULT_SCOPES;

  return {
    name: 'vite-plugin-highlight-github-dark-scope',
    enforce: 'pre',
    transform(code, id) {
      const pathOnly = id.split('?')[0];
      if (!pathOnly.endsWith('github-dark.css')) {
        return null;
      }
      if (!pathOnly.includes('highlight.js')) {
        return null;
      }

      const root = postcss.parse(code);
      root.walkRules(rule => {
        if (isInsideKeyframes(rule)) {
          return;
        }
        const parts = rule.selectors;
        if (!parts.length) {
          return;
        }
        rule.selector = parts.flatMap(part => scopes.map(scope => `${scope} ${part.trim()}`)).join(', ');
      });

      return {
        code: root.toString(),
        map: null,
      };
    },
  };
};
