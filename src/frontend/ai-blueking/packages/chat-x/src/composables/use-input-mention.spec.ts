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
import { defineComponent, h, nextTick } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { useInputMentionConsumer, useInputMentionProvider } from './use-input-mention';

import type { InputMentionContext } from './use-input-mention';

describe('useInputMention', () => {
  it('没有 Provider 时消费方拿到 undefined，据此可隐藏引用入口', () => {
    let mention: InputMentionContext | undefined;
    const wrapper = mount(
      defineComponent({
        setup() {
          mention = useInputMentionConsumer();
          return () => h('div');
        },
      }),
    );

    expect(mention).toBeUndefined();
    wrapper.unmount();
  });

  it('Provider 下游任意深度都能拿到 insertMention', async () => {
    const insertMention = vi.fn();
    let mention: InputMentionContext | undefined;

    const Child = defineComponent({
      setup() {
        mention = useInputMentionConsumer();
        return () => h('div');
      },
    });
    const wrapper = mount(
      defineComponent({
        setup() {
          useInputMentionProvider({ insertMention });
          return () => h(Child);
        },
      }),
    );
    await nextTick();

    mention?.insertMention({ id: 'o1', type: 'artifact', name: 'a.md' });
    expect(insertMention).toHaveBeenCalledWith({ id: 'o1', type: 'artifact', name: 'a.md' });
    wrapper.unmount();
  });
});
