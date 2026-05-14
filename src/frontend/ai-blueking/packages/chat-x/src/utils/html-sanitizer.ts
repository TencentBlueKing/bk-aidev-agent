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
import { sanitizeCSS } from './css-sanitizer';

const DANGEROUS_HTML_PATTERNS = [
  /<\s*script[^>]*>[\s\S]*?<\s*\/\s*script\s*>/gi,
  /<\s*script[^>]*>/gi,
  /on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi,
  /javascript\s*:/gi,
];

/**
 * 轻量级 HTML 片段净化，不自动闭合标签。
 * 用于流式渲染中 html_inline / html_block token 的净化——
 * DOMPurify 会把孤立的 `<font color="red">` 补成 `<font color="red"></font>`，
 * 导致后续内容无法继承样式，因此流式场景需要使用此函数。
 */
export const sanitizeHtmlFragment = (html: string): string => {
  let result = html.replace(/\0/g, '');
  for (const pattern of DANGEROUS_HTML_PATTERNS) {
    result = result.replace(pattern, '');
  }
  return result.replace(/\sstyle="([^"]*)"/gi, (_match, value) => {
    const safeCss = sanitizeCSS(value);
    return safeCss ? ` style="${safeCss}"` : '';
  });
};
