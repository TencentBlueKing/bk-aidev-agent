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
import { computed, defineComponent, h, nextTick } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import { GLOBAL_CONFIG_TOKEN, injectGlobalConfig, useGlobalConfig } from './use-global-config';

describe('use-global-config', () => {
  describe('GLOBAL_CONFIG_TOKEN', () => {
    it('应为 Symbol 类型', () => {
      expect(typeof GLOBAL_CONFIG_TOKEN).toBe('symbol');
    });
  });

  describe('useGlobalConfig', () => {
    it('调用后应通过 provide 将 options 交给后代（子组件 inject 与入参为同一引用）', async () => {
      const supportUpload = computed(() => true);
      const options = { supportUpload };
      let injected: ReturnType<typeof injectGlobalConfig> | undefined;

      const Child = defineComponent({
        setup() {
          injected = injectGlobalConfig();
          return {};
        },
        render() {
          return h('div');
        },
      });

      const Parent = defineComponent({
        setup() {
          useGlobalConfig(options);
          return {};
        },
        render() {
          return h(Child);
        },
      });

      const wrapper = mount(Parent);
      await nextTick();
      expect(injected).toBe(options);
      wrapper.unmount();
    });

    it('返回值应包含与入参一致的 supportUpload', () => {
      let returned: ReturnType<typeof useGlobalConfig> | undefined;
      const supportUpload = computed(() => false);

      const Parent = defineComponent({
        setup() {
          returned = useGlobalConfig({ supportUpload });
          return {};
        },
        render() {
          return h('div');
        },
      });

      mount(Parent);
      expect(returned?.supportUpload).toBe(supportUpload);
      expect(returned?.supportUpload?.value).toBe(false);
    });

    it('应透传 size 配置给后代', async () => {
      const size = computed<'normal' | 'small'>(() => 'normal');
      const supportUpload = computed(() => false);
      let injected: ReturnType<typeof injectGlobalConfig> | undefined;

      const Child = defineComponent({
        setup() {
          injected = injectGlobalConfig();
          return {};
        },
        render() {
          return h('div');
        },
      });
      const Parent = defineComponent({
        setup() {
          useGlobalConfig({ supportUpload, size });
          return {};
        },
        render() {
          return h(Child);
        },
      });

      const wrapper = mount(Parent);
      await nextTick();
      expect(injected?.size?.value).toBe('normal');
      wrapper.unmount();
    });

    it('应透传 timezone 配置给后代', async () => {
      const timezone = computed<string | undefined>(() => 'Asia/Shanghai');
      const supportUpload = computed(() => false);
      let injected: ReturnType<typeof injectGlobalConfig> | undefined;

      const Child = defineComponent({
        setup() {
          injected = injectGlobalConfig();
          return {};
        },
        render() {
          return h('div');
        },
      });
      const Parent = defineComponent({
        setup() {
          useGlobalConfig({ supportUpload, timezone });
          return {};
        },
        render() {
          return h(Child);
        },
      });

      const wrapper = mount(Parent);
      await nextTick();
      expect(injected?.timezone?.value).toBe('Asia/Shanghai');
      wrapper.unmount();
    });
  });

  describe('injectGlobalConfig', () => {
    it('有 Provider 时子组件应能 inject 到相同配置', async () => {
      let injected: ReturnType<typeof injectGlobalConfig> | undefined;
      const supportUpload = computed(() => true);

      const Child = defineComponent({
        setup() {
          injected = injectGlobalConfig();
          return {};
        },
        render() {
          return h('div');
        },
      });

      const Parent = defineComponent({
        setup() {
          useGlobalConfig({ supportUpload });
          return {};
        },
        render() {
          return h(Child);
        },
      });

      const wrapper = mount(Parent);
      await nextTick();
      expect(injected?.supportUpload).toBe(supportUpload);
      expect(injected?.supportUpload?.value).toBe(true);
      wrapper.unmount();
    });

    it('无 Provider 时应返回 undefined', () => {
      let injected: ReturnType<typeof injectGlobalConfig> | undefined;

      const Child = defineComponent({
        setup() {
          injected = injectGlobalConfig();
          return {};
        },
        render() {
          return h('div');
        },
      });

      const wrapper = mount(Child);
      expect(injected).toBeUndefined();
      wrapper.unmount();
    });
  });
});
