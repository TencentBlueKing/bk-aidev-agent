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
 * 蓝鲸行内富文本（安全样式）扩展。
 *
 * 语法（与 HTML 无关，不开启 markdown-it `html`）：
 *
 *   ::bk{ 属性列表 } 正文内容 :/bk::
 *
 * - 属性列表：写在 `{}` 内，使用 `;` 分隔，每项为 `键=值` 或 `键:值`（等号与冒号等价）。
 * - 正文：支持行内 Markdown（加粗、链接、行内代码等），由 markdown-it 再次 tokenize。
 * - 结束标记固定为 `:/bk::`，请勿在正文中使用该字面量。
 *
 * 支持的键（仅生成固定白名单 style）：
 * - `color` / `c`：颜色（#rgb / #rrggbb 或 CSS 命名色）
 * - `background-color`：背景色，规则同 color
 * - `font-size`：字号，如 `14px`（限制 1-72px）
 * - `bold`：加粗
 * - `italic`：斜体
 */

import type { PluginSimple } from '../markdown-it';
import type StateInline from 'markdown-it/lib/rules_inline/state_inline.mjs';

const MARK_OPEN = '::bk{';
const MARK_CLOSE = ':/bk::';

const sanitizeColor = (raw: string): null | string => {
  const v = raw.trim();
  if (!v) return null;
  if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v)) return v;
  if (/^[a-zA-Z][a-zA-Z-]*$/.test(v)) return v.toLowerCase();
  return null;
};

const sanitizeFontSize = (raw: string): null | string => {
  const m = raw.trim().match(/^(\d{1,2})px$/i);
  if (!m) return null;
  const n = Number.parseInt(m[1] ?? '', 10);
  if (Number.isNaN(n) || n <= 0 || n > 72) return null;
  return `${n}px`;
};

const buildStyleFromAttrSource = (attrSource: string): string => {
  const chunks: string[] = [];
  for (const part of attrSource.split(';')) {
    const seg = part.trim();
    if (!seg) continue;
    const sepIdx = seg.search(/[:=]/);
    if (sepIdx === -1) {
      const key = seg.toLowerCase();
      if (key === 'bold') chunks.push('font-weight: 700');
      else if (key === 'italic') chunks.push('font-style: italic');
      continue;
    }
    const keyRaw = seg.slice(0, sepIdx).trim().toLowerCase();
    const valRaw = seg.slice(sepIdx + 1).trim();

    if (keyRaw === 'color' || keyRaw === 'c') {
      const safe = sanitizeColor(valRaw);
      if (safe) chunks.push(`color: ${safe}`);
    } else if (keyRaw === 'background-color') {
      const safe = sanitizeColor(valRaw);
      if (safe) chunks.push(`background-color: ${safe}`);
    } else if (keyRaw === 'font-size') {
      const safe = sanitizeFontSize(valRaw);
      if (safe) chunks.push(`font-size: ${safe}`);
    }
  }
  return chunks.join('; ');
};

const bkInlineStyleRule = (state: StateInline, silent: boolean): boolean => {
  const src = state.src;
  const pos = state.pos;
  const max = state.posMax;

  if (pos + MARK_OPEN.length > max) return false;
  if (src.slice(pos, pos + MARK_OPEN.length) !== MARK_OPEN) return false;

  const attrsStart = pos + MARK_OPEN.length;
  const braceClose = src.indexOf('}', attrsStart);
  if (braceClose === -1 || braceClose > max) return false;

  const attrStr = src.slice(attrsStart, braceClose);
  const bodyStart = braceClose + 1;
  const closeIdx = src.indexOf(MARK_CLOSE, bodyStart);
  if (closeIdx === -1 || closeIdx > max) return false;

  const style = buildStyleFromAttrSource(attrStr);
  if (!style) return false;

  if (!silent) {
    const tokenOpen = state.push('span_open', 'span', 1);
    tokenOpen.attrs = [
      ['style', style],
      ['class', 'bk-md-inline-style'],
    ];

    const oldMax = state.posMax;
    state.pos = bodyStart;
    state.posMax = closeIdx;
    state.md.inline.tokenize(state);
    state.posMax = oldMax;

    state.push('span_close', 'span', -1);
  }

  state.pos = closeIdx + MARK_CLOSE.length;
  return true;
};

export const markdownItBkInlineStyle: PluginSimple = md => {
  md.inline.ruler.before('text', 'bk_inline_style', bkInlineStyleRule);
};
