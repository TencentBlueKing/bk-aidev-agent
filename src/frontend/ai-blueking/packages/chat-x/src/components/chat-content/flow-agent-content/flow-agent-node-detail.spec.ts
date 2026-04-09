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
import { defineComponent, h } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import FlowAgentNodeDetail from './flow-agent-node-detail.vue';

vi.mock('../../../icons', () => ({
  NodeOutputIcon: defineComponent({
    name: 'NodeOutputIcon',
    setup() {
      return () => h('span', { class: 'mock-node-output-icon' });
    },
  }),
  NodeTabIcon: defineComponent({
    name: 'NodeTabIcon',
    setup() {
      return () => h('span', { class: 'mock-node-tab-icon' });
    },
  }),
}));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('./detail-section.vue', () => ({
  default: defineComponent({
    name: 'DetailSection',
    props: { title: { type: String, default: '' } },
    setup(props, { slots }) {
      return () => h('div', { class: 'mock-detail-section', 'data-title': props.title }, slots.default?.());
    },
  }),
}));

vi.mock('./simple-table.vue', () => ({
  default: defineComponent({
    name: 'SimpleTable',
    props: {
      columns: { type: Array, default: () => [] },
      data: { type: Array, default: () => [] },
    },
    setup(props) {
      return () => h('div', { class: 'mock-simple-table', 'data-row-count': (props.data as unknown[]).length });
    },
  }),
}));

vi.mock('../../../common/lang', () => ({
  isEn: false,
}));

const baseProps = {
  loading: false,
  node_id: 'node-1',
  node_name: '测试节点',
  task_id: 123,
  task_name: '测试任务',
  data: {},
};

describe('FlowAgentNodeDetail', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: baseProps,
      });

      expect(wrapper.find('.flow-agent-node-detail').exists()).toBe(true);
    });

    it('应该渲染节点标题', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            basic_info: {
              node_name: '我的节点',
              template_name: '模板A',
              stage_name: '步骤1',
              optional: false,
            },
          },
        },
      });

      expect(wrapper.find('.detail-title').text()).toContain('节点');
      expect(wrapper.find('.detail-title').text()).toContain('我的节点');
    });

    it('loading 时应该渲染骨架屏', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: { ...baseProps, loading: true },
      });

      expect(wrapper.findAll('.ai-skeleton-element').length).toBeGreaterThan(0);
    });
  });

  describe('Tab 切换测试', () => {
    it('默认应该显示节点配置 Tab', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: baseProps,
      });

      const tabs = wrapper.findAll('.detail-tab');
      expect(tabs.length).toBe(2);
      expect(tabs[0]?.classes()).toContain('is-active');
    });

    it('点击节点输出 Tab 应切换', async () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: { outputs: [{ key: 'result', value: 'success' }] },
        },
      });

      const tabs = wrapper.findAll('.detail-tab');
      await tabs[1]?.trigger('click');

      expect(tabs[1]?.classes()).toContain('is-active');
    });
  });

  describe('基础信息测试', () => {
    it('应该正确渲染基础信息行', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            basic_info: {
              template_name: '流程模板A',
              node_name: '节点1',
              stage_name: '步骤1',
              optional: true,
            },
          },
        },
      });

      const infoRows = wrapper.findAll('.info-row');
      expect(infoRows.length).toBeGreaterThan(0);
    });

    it('应该正确显示失败处理信息', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            basic_info: {
              template_name: 'T',
              node_name: 'N',
              stage_name: 'S',
              optional: false,
              skippable: true,
              auto_retry: { enable: true, interval: 5, times: 3 },
            },
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain('手动跳过');
      expect(text).toContain('5');
      expect(text).toContain('3');
    });

    it('无失败处理时应该显示 --', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            basic_info: {
              template_name: 'T',
              node_name: 'N',
              stage_name: 'S',
              optional: false,
              skippable: false,
            },
          },
        },
      });

      const failureRow = wrapper.findAll('.info-row').find(r => r.find('.info-label').text().includes('失败处理'));
      expect(failureRow?.find('.info-value').text()).toBe('--');
    });
  });

  describe('超时控制测试', () => {
    it('启用超时控制时应该显示超时信息', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            basic_info: {
              template_name: 'T',
              node_name: 'N',
              stage_name: 'S',
              optional: false,
              timeout_config: {
                enable: true,
                seconds: 300,
                action: 'forced_fail',
              },
            },
          },
        },
      });

      const timeoutRow = wrapper.findAll('.info-row').find(r => r.find('.info-label').text().includes('超时控制'));
      expect(timeoutRow?.find('.info-value').text()).toContain('300');
      expect(timeoutRow?.find('.info-value').text()).toContain('强制失败');
    });

    it('未启用超时控制时应该显示 --', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            basic_info: {
              template_name: 'T',
              node_name: 'N',
              stage_name: 'S',
              optional: false,
            },
          },
        },
      });

      const timeoutRow = wrapper.findAll('.info-row').find(r => r.find('.info-label').text().includes('超时控制'));
      expect(timeoutRow?.find('.info-value').text()).toBe('--');
    });
  });

  describe('表格数据测试', () => {
    it('应该渲染输入参数表格', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: {
          ...baseProps,
          data: {
            inputs: { param1: 'value1', param2: 'value2' },
          },
        },
      });

      const sections = wrapper.findAll('.mock-detail-section');
      const inputSection = sections.find(s => s.attributes('data-title') === '输入参数');
      expect(inputSection).toBeTruthy();

      const table = inputSection?.find('.mock-simple-table');
      expect(table?.attributes('data-row-count')).toBe('2');
    });

    it('data 为空对象时表格应该无数据', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: baseProps,
      });

      const sections = wrapper.findAll('.mock-detail-section');
      const inputSection = sections.find(s => s.attributes('data-title') === '输入参数');
      const table = inputSection?.find('.mock-simple-table');
      expect(table?.attributes('data-row-count')).toBe('0');
    });
  });

  describe('边界情况测试', () => {
    it('data 为空对象时应该正常渲染', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: baseProps,
      });

      expect(wrapper.find('.flow-agent-node-detail').exists()).toBe(true);
    });

    it('loading 时不应该渲染数据内容', () => {
      wrapper = mount(FlowAgentNodeDetail, {
        props: { ...baseProps, loading: true },
      });

      expect(wrapper.find('.mock-detail-section').exists()).toBe(false);
    });
  });
});
