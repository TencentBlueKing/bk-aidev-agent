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

import ActivityMessage from './activity-message.vue';

vi.mock('../../../icons/content', () => ({
  DocumentIcon: defineComponent({
    name: 'DocumentIcon',
    setup() {
      return () => h('span', { class: 'mock-document-icon' });
    },
  }),
}));

vi.mock('../../../icons/messages', () => ({
  CollapsedIcon: defineComponent({
    name: 'CollapsedIcon',
    setup() {
      return () => h('span', { class: 'mock-collapsed-icon' });
    },
  }),
}));

vi.mock('../../ai-loading/ai-loading.vue', () => ({
  default: defineComponent({
    name: 'AiLoading',
    props: {
      size: { type: Number, default: 16 },
      stopLoading: { type: Boolean, default: false },
    },
    setup() {
      return () => h('span', { class: 'mock-ai-loading' });
    },
  }),
}));

vi.mock('../../chat-content/markdown-content/markdown-content.vue', () => ({
  default: defineComponent({
    name: 'MarkdownContent',
    props: {
      content: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-markdown-content' }, props.content);
    },
  }),
}));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../../ag-ui/types/constants', () => ({
  MessageContentType: {
    FlowAgent: 'flow_agent',
    KnowledgeRag: 'knowledge_rag',
    ReferenceDocument: 'reference_document',
  },
  MessageStatus: {
    Pending: 'pending',
    Streaming: 'streaming',
    Complete: 'complete',
  },
}));

vi.mock('../../chat-content/flow-agent-content/flow-agent-content.vue', () => ({
  default: defineComponent({
    name: 'FlowAgentContent',
    props: {
      content: { type: Object, default: () => ({}) },
      status: { type: String, default: '' },
      collapsed: { type: Boolean, default: false },
      messageUid: { type: String, default: '' },
      onInterruptResume: { type: Function, default: undefined },
    },
    emits: ['update:collapsed'],
    setup(props) {
      return () =>
        h(
          'div',
          {
            class: 'mock-flow-agent-content',
            'data-status': props.status,
            'data-message-uid': props.messageUid || '',
            'data-has-on-interrupt-resume': props.onInterruptResume ? 'true' : undefined,
          },
          'FlowAgentContent',
        );
    },
  }),
}));

vi.mock('../../chat-content/reference-content/reference-content.vue', () => ({
  default: defineComponent({
    name: 'ReferenceContent',
    props: {
      content: { type: Array, default: () => [] },
    },
    setup(props) {
      return () => h('div', { class: 'mock-reference-content', 'data-length': props.content?.length || 0 });
    },
  }),
}));

vi.mock('../../../common/lang', () => ({
  isEn: false,
}));

describe('ActivityMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('调度器测试', () => {
    it('未知的 activityType 不应该渲染任何内容', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'unknown_type',
        },
      });

      expect(wrapper.find('.ai-activity-message').exists()).toBe(false);
    });

    it('未提供 activityType 不应该渲染任何内容', () => {
      wrapper = mount(ActivityMessage, {
        props: {},
      });

      expect(wrapper.find('.ai-activity-message').exists()).toBe(false);
    });
  });

  describe('ReferenceDocument 类型测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.ai-activity-message').exists()).toBe(true);
    });

    it('应该渲染标题区域', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.ai-activity-message-title').exists()).toBe(true);
    });

    it('应该渲染 DocumentIcon', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.mock-document-icon').exists()).toBe(true);
    });

    it('应该渲染 CollapsedIcon', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.mock-collapsed-icon').exists()).toBe(true);
    });

    it('应该正确显示引用文档数量', () => {
      const content = [
        { name: '文档1', url: 'https://example1.com', originFile: '' },
        { name: '文档2', url: 'https://example2.com', originFile: '' },
        { name: '文档3', url: 'https://example3.com', originFile: '' },
      ];

      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content,
        },
      });

      expect(wrapper.find('.ai-activity-message-title-text').text()).toContain('3');
    });

    it('应该渲染 ReferenceContent 组件', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.mock-reference-content').exists()).toBe(true);
    });

    it('应该处理空的 content 数组', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [],
        },
      });

      expect(wrapper.find('.ai-activity-message').exists()).toBe(true);
    });
  });

  describe('折叠功能测试', () => {
    it('默认应该展开显示内容', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.ai-activity-message-content').isVisible()).toBe(true);
    });

    it('点击标题应该切换折叠状态', async () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
          collapsed: false,
          'onUpdate:collapsed': (val: boolean) => wrapper.setProps({ collapsed: val }),
        },
      });

      expect(wrapper.find('.ai-activity-message-content').isVisible()).toBe(true);

      await wrapper.find('.ai-activity-message-title').trigger('click');

      expect(wrapper.emitted('update:collapsed')).toBeTruthy();
    });

    it('折叠时 collapsed-icon 应该有 is-collapsed 类', async () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      await wrapper.find('.ai-activity-message-title').trigger('click');

      expect(wrapper.find('.collapsed-icon').classes()).toContain('is-collapsed');
    });
  });

  describe('KnowledgeRag 类型测试', () => {
    it('activityType 为 knowledge_rag 且 status 为 pending 时应该渲染 AiLoading', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'knowledge_rag',
          status: 'pending',
          content: {
            content: '检索内容',
            referenceDocument: [],
          },
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(true);
      expect(wrapper.find('.mock-document-icon').exists()).toBe(false);
    });

    it('activityType 为 knowledge_rag 且无 status 时应该显示 DocumentIcon', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'knowledge_rag',
          content: {
            content: '检索内容',
            referenceDocument: [],
          },
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(false);
      expect(wrapper.find('.mock-document-icon').exists()).toBe(true);
    });

    it('activityType 为 knowledge_rag 且 status 为 pending 时应该显示检索中', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'knowledge_rag',
          status: 'pending',
          content: {
            content: '检索内容',
            referenceDocument: [],
          },
        },
      });

      expect(wrapper.find('.ai-activity-message-title-text').text()).toBe('检索中');
    });

    it('activityType 为 knowledge_rag 且 status 为 streaming 时应该显示检索中', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'knowledge_rag',
          status: 'streaming',
          content: {
            content: '检索内容',
            referenceDocument: [],
          },
        },
      });

      expect(wrapper.find('.ai-activity-message-title-text').text()).toBe('检索中');
    });

    it('activityType 为 knowledge_rag 且 status 为 complete 时应该显示检索完成', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'knowledge_rag',
          status: 'complete',
          content: {
            content: '检索内容',
            referenceDocument: [],
          },
        },
      });

      expect(wrapper.find('.ai-activity-message-title-text').text()).toBe('检索完成');
    });

    it('activityType 为 knowledge_rag 时应该渲染 MarkdownContent', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'knowledge_rag',
          content: {
            content: '这是检索内容',
            referenceDocument: [],
          },
        },
      });

      expect(wrapper.find('.ai-knowledge-rag-content').exists()).toBe(true);
      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('activityType 非 knowledge_rag 时不应该渲染 knowledge-rag-content', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.ai-knowledge-rag-content').exists()).toBe(false);
      expect(wrapper.find('.mock-document-icon').exists()).toBe(true);
    });

    it('status 为 pending 且非 knowledge_rag 时应该显示 DocumentIcon', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          status: 'pending',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(false);
      expect(wrapper.find('.mock-document-icon').exists()).toBe(true);
    });
  });

  describe('FlowAgent 类型测试', () => {
    it('应该渲染 FlowAgentContent', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'flow_agent',
          content: [],
        },
      });

      expect(wrapper.find('.mock-flow-agent-content').exists()).toBe(true);
    });

    it('应该将 content 和 status 传递给 FlowAgentContent', () => {
      const content = [{ task_name: '测试任务', nodes: {} }];
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'flow_agent',
          content,
          status: 'streaming',
        },
      });

      expect(wrapper.find('.mock-flow-agent-content').attributes('data-status')).toBe('streaming');
    });

    it('应将 uid 作为 messageUid 传递给 FlowAgentContent', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'flow_agent',
          content: [],
          uid: 'activity-uid-1',
        },
      });

      expect(wrapper.find('.mock-flow-agent-content').attributes('data-message-uid')).toBe('activity-uid-1');
    });

    it('应将 onInterruptResume 传递给 FlowAgentContent', () => {
      const onInterruptResume = vi.fn();
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'flow_agent',
          content: [],
          onInterruptResume,
        },
      });

      expect(wrapper.find('.mock-flow-agent-content').attributes('data-has-on-interrupt-resume')).toBe('true');
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(ActivityMessage, {
        props: {
          activityType: 'reference_document',
          content: [{ name: '文档1', url: 'https://example.com', originFile: '' }],
        },
      });

      expect(wrapper.find('.ai-activity-message').exists()).toBe(true);
      expect(wrapper.find('.ai-activity-message-title').exists()).toBe(true);
      expect(wrapper.find('.ai-activity-message-content').exists()).toBe(true);
    });
  });
});
