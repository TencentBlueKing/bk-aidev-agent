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
import { describe, expect, it } from 'vitest';

import { EDITOR_MENU_Z_INDEX } from '../../../common';
import { createModelDescriptionTippy, MODEL_DESCRIPTION_TIP_DELAY_MS } from './create-model-description-tippy';

import type { GetReferenceClientRect } from 'tippy.js';

describe('createModelDescriptionTippy', () => {
  const getReferenceClientRect = (() => new DOMRect()) as GetReferenceClientRect;

  it('应复用 ai-chat-box，并挂到 body 上以免被列表裁切', () => {
    const options = createModelDescriptionTippy(getReferenceClientRect);
    const appendTo = options.appendTo as () => HTMLElement;

    expect(MODEL_DESCRIPTION_TIP_DELAY_MS).toBe(300);
    expect(options.getReferenceClientRect).toBe(getReferenceClientRect);
    expect(appendTo()).toBe(document.body);
    expect(options).toMatchObject({
      allowHTML: false,
      arrow: true,
      content: '',
      delay: [0, 0],
      interactive: false,
      offset: [0, 8],
      placement: 'auto',
      popperOptions: { strategy: 'fixed' },
      theme: 'ai-chat-box',
      trigger: 'manual',
      zIndex: EDITOR_MENU_Z_INDEX,
    });
  });

  it('应采用外层 common tippy 的 appendTo、placement、zIndex，且不改描述气泡自己的触发方式', () => {
    const host = document.createElement('div');
    const appendTo = () => host;
    const options = createModelDescriptionTippy(getReferenceClientRect, {
      appendTo,
      placement: 'bottom-start',
      zIndex: 20,
    });

    expect(options.appendTo).toBe(appendTo);
    expect(options.placement).toBe('bottom-start');
    expect(options.zIndex).toBe(20);
    expect(options.trigger).toBe('manual');
    expect(options.interactive).toBe(false);
  });
});
