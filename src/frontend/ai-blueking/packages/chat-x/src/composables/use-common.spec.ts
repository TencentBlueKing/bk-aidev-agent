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
import { type ComputedRef, computed, defineComponent, h, nextTick, shallowRef } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import { RenderMode } from '../common/constants';
import {
  useCommonTippyInject,
  useCommonTippyProvider,
  useRenderModeInject,
  useRenderModeProvider,
} from './use-common';

import type { AITippyProps } from '../types';

describe('use-common', () => {
  describe('useCommonTippyProvider / useCommonTippyInject', () => {
    it('子组件应能 inject 到父组件提供的 tippy 配置', async () => {
      let injected: ComputedRef<AITippyProps | undefined> | undefined;

      const Child = defineComponent({
        setup() {
          injected = useCommonTippyInject();
          return {};
        },
        render() {
          return h('div');
        },
      });

      const tippyOptions = computed<Partial<AITippyProps> | undefined>(() => ({
        placement: 'bottom',
      }));

      const Parent = defineComponent({
        setup() {
          useCommonTippyProvider({ tippyOptions });
          return {};
        },
        render() {
          return h(Child);
        },
      });

      const wrapper = mount(Parent);
      await nextTick();

      expect(injected?.value).toEqual({ placement: 'bottom' });

      wrapper.unmount();
    });
  });

  describe('useRenderModeProvider / useRenderModeInject', () => {
    it('未提供 renderMode 时应返回 Chat 默认值', () => {
      let injected: ComputedRef<RenderMode> | undefined;

      const Child = defineComponent({
        setup() {
          injected = useRenderModeInject();
          return {};
        },
        render() {
          return h('div');
        },
      });

      const wrapper = mount(Child);

      expect(injected?.value).toBe(RenderMode.Chat);

      wrapper.unmount();
    });

    it('子组件应能 inject 到父组件提供的响应式 renderMode', async () => {
      let injected: ComputedRef<RenderMode> | undefined;
      const renderMode = shallowRef(RenderMode.Chat);

      const Child = defineComponent({
        setup() {
          injected = useRenderModeInject();
          return {};
        },
        render() {
          return h('div');
        },
      });

      const Parent = defineComponent({
        setup() {
          useRenderModeProvider({ renderMode });
          return {};
        },
        render() {
          return h(Child);
        },
      });

      const wrapper = mount(Parent);
      expect(injected?.value).toBe(RenderMode.Chat);

      renderMode.value = RenderMode.Share;
      await nextTick();
      expect(injected?.value).toBe(RenderMode.Share);

      wrapper.unmount();
    });
  });
});
