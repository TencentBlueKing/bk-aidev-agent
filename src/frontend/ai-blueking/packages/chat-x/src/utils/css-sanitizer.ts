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
const SAFE_CSS_PROPERTIES = new Set([
  'color',
  'font',
  'font-family',
  'font-size',
  'font-weight',
  'font-style',
  'font-variant',
  'line-height',
  'letter-spacing',
  'text-align',
  'text-decoration',
  'text-indent',
  'text-transform',
  'text-shadow',
  'white-space',
  'word-break',
  'word-spacing',
  'background',
  'background-color',
  'background-clip',
  'border',
  'border-color',
  'border-style',
  'border-width',
  'border-radius',
  'border-collapse',
  'border-spacing',
  'width',
  'height',
  'max-width',
  'max-height',
  'min-width',
  'min-height',
  'padding',
  'padding-top',
  'padding-right',
  'padding-bottom',
  'padding-left',
  'margin',
  'margin-top',
  'margin-right',
  'margin-bottom',
  'margin-left',
  'box-sizing',
  'box-shadow',
  'display',
  'overflow',
  'visibility',
  'opacity',
  'float',
  'clear',
  'vertical-align',
  'list-style',
  'list-style-type',
  'cursor',
  'direction',
]);

const DANGEROUS_CSS_PATTERNS = [
  /url\s*\(/i,
  /expression\s*\(/i,
  /javascript\s*:/i,
  /data:\s*/i,
  /progid\s*:/i,
  /-moz-binding/i,
  /behavior\s*:/i,
  /@import/i,
];

/**
 * 过滤 CSS 属性值，仅保留白名单中的安全属性，
 * 并拦截 url()、expression()、javascript: 等危险模式。
 *
 * 注意：此函数是第二道防线。第一道由 DOMPurify 处理（过滤 script/event handler/javascript: URI 等）。
 */
export const sanitizeCSS = (cssValue: string): string => {
  return cssValue
    .split(';')
    .map(decl => {
      const trimmed = decl.trim();
      if (!trimmed) return '';
      const colonIdx = trimmed.indexOf(':');
      if (colonIdx === -1) return '';
      const prop = trimmed.slice(0, colonIdx).trim().toLowerCase();
      const value = trimmed.slice(colonIdx + 1).trim();
      if (!SAFE_CSS_PROPERTIES.has(prop)) return '';
      for (const pattern of DANGEROUS_CSS_PATTERNS) {
        if (pattern.test(value)) return '';
      }
      return `${prop}: ${value}`;
    })
    .filter(Boolean)
    .join('; ');
};
