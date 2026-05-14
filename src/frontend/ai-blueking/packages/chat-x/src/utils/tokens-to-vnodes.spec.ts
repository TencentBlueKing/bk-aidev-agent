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
import { describe, expect, it, vi } from 'vitest';

import type { Options, Renderer, Token } from '../markdown-it';
import { tokensToVNodes } from './tokens-to-vnodes';

const makeHtmlToken = (content: string, type: 'html_inline' | 'html_block' = 'html_inline'): Token =>
  ({
    type,
    tag: '',
    nesting: 0,
    content,
    children: null,
    hidden: false,
    level: 0,
    markup: '',
    info: '',
    meta: null,
    block: false,
    attrs: null,
    map: null,
    attrIndex: () => -1,
    attrPush: () => {},
    attrSet: () => {},
    attrGet: () => null,
    attrJoin: () => {},
  }) as unknown as Token;

const makeTextToken = (content: string): Token =>
  ({
    type: 'text',
    tag: '',
    nesting: 0,
    content,
    children: null,
    hidden: false,
    level: 0,
    markup: '',
    info: '',
    meta: null,
    block: false,
    attrs: null,
    map: null,
    attrIndex: () => -1,
    attrPush: () => {},
    attrSet: () => {},
    attrGet: () => null,
    attrJoin: () => {},
  }) as unknown as Token;

const makeInlineToken = (children: Token[]): Token =>
  ({
    type: 'inline',
    tag: '',
    nesting: 0,
    content: '',
    children,
    hidden: false,
    level: 0,
    markup: '',
    info: '',
    meta: null,
    block: false,
    attrs: null,
    map: null,
    attrIndex: () => -1,
    attrPush: () => {},
    attrSet: () => {},
    attrGet: () => null,
    attrJoin: () => {},
  }) as unknown as Token;

describe('tokensToVNodes', () => {
  describe('renderer.rules 自定义块', () => {
    it('应将 mditOptions 作为规则第三参传入 markdown-it 规则', () => {
      const mditOptions = { breaks: true } as Options;
      const rule = vi.fn((_tokens: Token[], _idx: number, options: Options) => {
        expect(options).toBe(mditOptions);
        return '<span class="rule-out">x</span>';
      });

      const renderer = {
        rules: {
          plugin_block: rule,
        },
      } as unknown as Renderer;

      const token = {
        type: 'plugin_block',
        nesting: 0,
        tag: '',
        hidden: false,
      } as Token;

      tokensToVNodes([token], {
        renderer,
        mditOptions,
        sanitize: html => html,
      });

      expect(rule).toHaveBeenCalledTimes(1);
    });
  });

  describe('mergeHtmlInlineTokens - HTML 标签合并', () => {
    const render = (tokens: Token[]) =>
      tokensToVNodes([makeInlineToken(tokens)], { html: true, sanitizeHtmlFragment: (h: string) => h });

    it('合并连续的 html_inline token 为单个 span', () => {
      const tokens = [
        makeHtmlToken('<font color="red">'),
        makeHtmlToken('<b>'),
        makeTextToken('标题'),
        makeHtmlToken('</b>'),
        makeHtmlToken('</font>'),
      ];
      const vnodes = render(tokens);
      expect(vnodes).toHaveLength(1);
      expect(vnodes[0].props.innerHTML).toBe('<font color="red"><b>标题</b></font>');
    });

    it('不合并非连续的 html_inline token', () => {
      const softbreak = {
        type: 'softbreak',
        tag: '',
        nesting: 0,
        content: '',
        children: null,
        hidden: false,
        level: 0,
        markup: '',
        info: '',
        meta: null,
        block: false,
        attrs: null,
        map: null,
        attrIndex: () => -1,
        attrPush: () => {},
        attrSet: () => {},
        attrGet: () => null,
        attrJoin: () => {},
      } as unknown as Token;
      const tokens = [
        makeHtmlToken('<b>'),
        makeTextToken('A'),
        makeHtmlToken('</b>'),
        softbreak,
        makeHtmlToken('<div>'),
        makeTextToken('B'),
        makeHtmlToken('</div>'),
      ];
      const vnodes = render(tokens);
      expect(vnodes.length).toBeGreaterThan(1);
    });

    it('单个 html_inline token 不受影响', () => {
      const tokens = [makeHtmlToken('<br>')];
      const vnodes = render(tokens);
      expect(vnodes).toHaveLength(1);
      expect(vnodes[0].props.innerHTML).toBe('<br>');
    });

    it('合并时保留 html_block 语义', () => {
      const tokens = [
        makeHtmlToken('<div>', 'html_block'),
        makeTextToken('content'),
        makeHtmlToken('</div>', 'html_block'),
      ];
      const vnodes = render(tokens);
      expect(vnodes).toHaveLength(1);
      expect(vnodes[0].type).toBe('div');
      expect(vnodes[0].props.innerHTML).toBe('<div>content</div>');
    });
  });
});
