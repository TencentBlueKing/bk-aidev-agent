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
});
