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

import { EDITOR_MENU_Z_INDEX } from '../../common';
import { createMentionTippy } from './create-mention-tippy';

import type { Instance } from 'tippy.js';

describe('createMentionTippy', () => {
  it('气泡内容为标题 + 描述，并带上设计稿约定的交互参数', () => {
    const options = createMentionTippy({ title: '工具：knowlege-base', description: '描述介绍' });
    const content = options.content as { props?: Record<string, unknown> };

    expect(content.props).toMatchObject({ title: '工具：knowlege-base', description: '描述介绍' });
    expect(options).toMatchObject({
      arrow: true,
      delay: [300, 0],
      hideOnClick: false,
      interactive: false,
      offset: [0, 8],
      placement: 'top',
      theme: 'light ai-mention-popover-theme',
      trigger: 'mouseenter focus click',
      zIndex: EDITOR_MENU_Z_INDEX,
    });
  });

  it('点击外部时关闭气泡，点击标签本身不因 hideOnClick 收起', () => {
    const options = createMentionTippy({ title: '工具：a' });
    const hide = vi.fn();

    expect(options.hideOnClick).toBe(false);
    options.onClickOutside?.({ hide } as unknown as Instance);
    expect(hide).toHaveBeenCalledTimes(1);
  });

  it('appendTo 挂到 document.body，避免被编辑器裁剪', () => {
    const options = createMentionTippy({ title: '工具：a' });
    const appendTo = options.appendTo as () => HTMLElement;
    expect(appendTo()).toBe(document.body);
  });
});
