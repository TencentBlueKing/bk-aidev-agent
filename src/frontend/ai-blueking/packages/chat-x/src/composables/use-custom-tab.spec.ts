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
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EXECUTION_TAB_NAME, useCustomTabConsumer, useCustomTabProvider } from './use-custom-tab';

vi.mock('../lang/lang', () => ({
  t: (key: string) => key,
}));

const createProviderComponent = (onTabChange?: (tab: unknown) => void) =>
  defineComponent({
    setup() {
      const result = useCustomTabProvider({ onTabChange });
      return { providerResult: result };
    },
    render() {
      return h('div', { class: 'provider' }, this.$slots.default?.());
    },
  });

const createConsumerComponent = () =>
  defineComponent({
    setup() {
      const result = useCustomTabConsumer();
      return { consumer: result };
    },
    render() {
      return h('div', { class: 'consumer' });
    },
  });

describe('useCustomTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useCustomTabProvider', () => {
    it('初始应该包含执行情况 Tab', () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as { providerResult: { tabs: { value: { name: string }[] } } };
      expect(vm.providerResult.tabs.value.length).toBe(1);
      expect(vm.providerResult.tabs.value[0]?.name).toBe(EXECUTION_TAB_NAME);

      wrapper.unmount();
    });

    it('初始应该折叠', () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as { providerResult: { isCollapse: { value: boolean } } };
      expect(vm.providerResult.isCollapse.value).toBe(true);

      wrapper.unmount();
    });

    it('addCustomTab 应该添加新 Tab 并展开', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          addCustomTab: (tab: { label: string; name: string }) => void;
          isCollapse: { value: boolean };
          tabs: { value: { name: string }[] };
        };
      };

      vm.providerResult.addCustomTab({ label: '节点详情', name: 'node-1' });
      await nextTick();

      expect(vm.providerResult.tabs.value.length).toBe(2);
      expect(vm.providerResult.tabs.value[1]?.name).toBe('node-1');
      expect(vm.providerResult.isCollapse.value).toBe(false);

      wrapper.unmount();
    });

    it('同名 Tab 不应该重复添加', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          addCustomTab: (tab: { label: string; name: string }) => void;
          tabs: { value: { name: string }[] };
        };
      };

      vm.providerResult.addCustomTab({ label: '节点1', name: 'node-1' });
      await nextTick();
      vm.providerResult.addCustomTab({ label: '节点1-重复', name: 'node-1' });
      await nextTick();

      expect(vm.providerResult.tabs.value.length).toBe(2);

      wrapper.unmount();
    });

    it('removeCustomTab 应该移除指定 Tab', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          addCustomTab: (tab: { label: string; name: string }) => void;
          removeCustomTab: (name: string) => void;
          tabs: { value: { name: string }[] };
        };
      };

      vm.providerResult.addCustomTab({ label: '节点1', name: 'node-1' });
      await nextTick();
      expect(vm.providerResult.tabs.value.length).toBe(2);

      vm.providerResult.removeCustomTab('node-1');
      expect(vm.providerResult.tabs.value.length).toBe(1);
      expect(vm.providerResult.tabs.value[0]?.name).toBe(EXECUTION_TAB_NAME);

      wrapper.unmount();
    });

    it('selectCustomTab 应该更新 selectedTab 并调用 onTabChange', async () => {
      const onTabChange = vi.fn();
      const Provider = createProviderComponent(onTabChange);
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          addCustomTab: (tab: { label: string; name: string }) => void;
        };
      };

      const newTab = { label: '节点1', name: 'node-1' };
      vm.providerResult.addCustomTab(newTab);
      await nextTick();
      await nextTick();

      expect(onTabChange).toHaveBeenCalledWith(newTab);

      wrapper.unmount();
    });

    it('resetCustomTab 应该恢复为仅执行情况 Tab、折叠并选中默认 Tab', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          addCustomTab: (tab: { label: string; name: string }) => void;
          resetCustomTab: () => void;
          tabs: { value: { name: string }[] };
          selectedTab: { value: { name: string } };
          isCollapse: { value: boolean };
        };
      };

      vm.providerResult.addCustomTab({ label: '节点1', name: 'node-1' });
      await nextTick();
      expect(vm.providerResult.tabs.value.length).toBe(2);
      expect(vm.providerResult.isCollapse.value).toBe(false);

      vm.providerResult.resetCustomTab();
      expect(vm.providerResult.tabs.value.length).toBe(1);
      expect(vm.providerResult.tabs.value[0]?.name).toBe(EXECUTION_TAB_NAME);
      expect(vm.providerResult.selectedTab.value.name).toBe(EXECUTION_TAB_NAME);
      expect(vm.providerResult.isCollapse.value).toBe(true);

      wrapper.unmount();
    });
  });

  describe('useCustomTabConsumer', () => {
    it('有 Provider 时应该返回 inject 的值', () => {
      const Provider = createProviderComponent();
      const Consumer = createConsumerComponent();

      const wrapper = mount(Provider, {
        slots: {
          default: () => h(Consumer),
        },
      });

      const consumerVm = wrapper.findComponent(Consumer).vm as unknown as { consumer: { tabs: unknown } };
      expect(consumerVm.consumer).toBeDefined();
      expect(consumerVm.consumer.tabs).toBeDefined();

      wrapper.unmount();
    });

    it('无 Provider 时应该返回 undefined', () => {
      const Consumer = createConsumerComponent();
      const wrapper = mount(Consumer);

      const vm = wrapper.vm as unknown as { consumer: unknown };
      expect(vm.consumer).toBeUndefined();

      wrapper.unmount();
    });
  });
});
