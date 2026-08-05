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
import { type Ref, defineComponent, h, nextTick, ref } from 'vue';

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

/** 支持注入 executionTabVisible（响应式）的 Provider，便于测试显隐与排序 */
const createConfigurableProvider = (executionVisible: Ref<boolean>) =>
  defineComponent({
    setup() {
      const result = useCustomTabProvider({
        executionTabVisible: () => executionVisible.value,
      });
      return { providerResult: result };
    },
    render() {
      return h('div', { class: 'provider' });
    },
  });

type ProviderVm = {
  providerResult: {
    addCustomTab: (tab: { label: string; name: string; order?: number; visible?: boolean }) => void;
    displayTabs: { value: { label: string; name: string }[] };
    selectCustomTab: (tab: { name: string }) => void;
    selectedTab: { value: { name: string } };
    tabs: { value: { label: string; name: string }[] };
  };
};

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

    it('ensureCustomTab 应挂上 Tab 但不展开、不切换选中', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          ensureCustomTab: (tab: { label: string; name: string }) => void;
          isCollapse: { value: boolean };
          selectedTab: { value: { name: string } };
          tabs: { value: { name: string }[] };
        };
      };

      vm.providerResult.ensureCustomTab({ label: '文件产物', name: 'file-artifact' });
      await nextTick();

      expect(vm.providerResult.tabs.value.some(tab => tab.name === 'file-artifact')).toBe(true);
      expect(vm.providerResult.isCollapse.value).toBe(true);
      expect(vm.providerResult.selectedTab.value.name).toBe(EXECUTION_TAB_NAME);

      wrapper.unmount();
    });

    it('ensureCustomTab 同名应合并更新且仍不展开、不切换选中', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);

      const vm = wrapper.vm as unknown as {
        providerResult: {
          ensureCustomTab: (tab: {
            label: string;
            name: string;
            order?: number;
            visible?: boolean;
          }) => void;
          isCollapse: { value: boolean };
          selectedTab: { value: { name: string } };
          tabs: { value: { label: string; name: string; order?: number }[] };
        };
      };

      vm.providerResult.ensureCustomTab({ label: '文件产物', name: 'file-artifact', order: -1 });
      await nextTick();
      vm.providerResult.ensureCustomTab({ label: '文件产物-更新', name: 'file-artifact', order: -2 });
      await nextTick();

      const fileTabs = vm.providerResult.tabs.value.filter(tab => tab.name === 'file-artifact');
      expect(fileTabs).toHaveLength(1);
      expect(fileTabs[0]).toMatchObject({ label: '文件产物-更新', order: -2 });
      expect(vm.providerResult.isCollapse.value).toBe(true);
      expect(vm.providerResult.selectedTab.value.name).toBe(EXECUTION_TAB_NAME);

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

  describe('displayTabs 排序与显隐', () => {
    it('displayTabs 应按 order 升序排序（执行情况 order 0 居首）', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);
      const vm = wrapper.vm as unknown as ProviderVm;

      vm.providerResult.addCustomTab({ label: 'A', name: 'a' }); // 默认 order 100
      await nextTick();
      vm.providerResult.addCustomTab({ label: 'B', name: 'b', order: 10 });
      await nextTick();

      expect(vm.providerResult.displayTabs.value.map(tab => tab.name)).toEqual([EXECUTION_TAB_NAME, 'b', 'a']);

      wrapper.unmount();
    });

    it('同 order 应保持插入顺序（稳定排序）', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);
      const vm = wrapper.vm as unknown as ProviderVm;

      vm.providerResult.addCustomTab({ label: 'A', name: 'a', order: 50 });
      await nextTick();
      vm.providerResult.addCustomTab({ label: 'B', name: 'b', order: 50 });
      await nextTick();

      expect(vm.providerResult.displayTabs.value.map(tab => tab.name)).toEqual([EXECUTION_TAB_NAME, 'a', 'b']);

      wrapper.unmount();
    });

    it('visible 为 false 的 Tab 不应出现在 displayTabs，但仍保留在 tabs', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);
      const vm = wrapper.vm as unknown as ProviderVm;

      vm.providerResult.addCustomTab({ label: '隐藏', name: 'hidden', visible: false });
      await nextTick();

      expect(vm.providerResult.tabs.value.some(tab => tab.name === 'hidden')).toBe(true);
      expect(vm.providerResult.displayTabs.value.some(tab => tab.name === 'hidden')).toBe(false);

      wrapper.unmount();
    });

    it('executionTabVisible 为 false 时执行情况不在 displayTabs', async () => {
      const executionVisible = ref(false);
      const Provider = createConfigurableProvider(executionVisible);
      const wrapper = mount(Provider);
      const vm = wrapper.vm as unknown as ProviderVm;

      expect(vm.providerResult.displayTabs.value.some(tab => tab.name === EXECUTION_TAB_NAME)).toBe(false);

      wrapper.unmount();
    });
  });

  describe('addCustomTab 合并更新', () => {
    it('同名 Tab 应合并更新 label / order / visible 而非追加', async () => {
      const Provider = createProviderComponent();
      const wrapper = mount(Provider);
      const vm = wrapper.vm as unknown as ProviderVm;

      vm.providerResult.addCustomTab({ label: 'L1', name: 'x' });
      await nextTick();
      vm.providerResult.addCustomTab({ label: 'L2', name: 'x', order: 5 });
      await nextTick();

      expect(vm.providerResult.tabs.value.length).toBe(2);
      const target = vm.providerResult.tabs.value.find(tab => tab.name === 'x') as { label: string; order?: number };
      expect(target.label).toBe('L2');
      expect(target.order).toBe(5);

      wrapper.unmount();
    });
  });

  describe('选中 Tab 被隐藏时回退', () => {
    it('当前选中的执行情况被配置隐藏时应自动切到首个可见 Tab', async () => {
      const executionVisible = ref(true);
      const Provider = createConfigurableProvider(executionVisible);
      const wrapper = mount(Provider);
      const vm = wrapper.vm as unknown as ProviderVm;

      vm.providerResult.addCustomTab({ label: '节点1', name: 'node-1' });
      await nextTick();
      // 回到执行情况 Tab
      vm.providerResult.selectCustomTab({ name: EXECUTION_TAB_NAME });
      expect(vm.providerResult.selectedTab.value.name).toBe(EXECUTION_TAB_NAME);

      // 隐藏执行情况 → 选中态应回退到唯一可见的 node-1
      executionVisible.value = false;
      await nextTick();

      expect(vm.providerResult.selectedTab.value.name).toBe('node-1');

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
