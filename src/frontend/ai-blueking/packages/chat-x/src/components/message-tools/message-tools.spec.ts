/* eslint-disable @typescript-eslint/no-explicit-any */
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

import { defineComponent, h, nextTick, ref } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageToolsStatus } from '../../types/tool';
import MessageTools from './message-tools.vue';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock vue-tippy：onShow 回调返回 false 时视为阻止展示，用于断言 handleTippyShow 行为
vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    props: {
      arrow: { type: Boolean, default: false },
      interactive: { type: Boolean, default: false },
      offset: { type: Array, default: () => [0, 0] },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'click' },
      onShow: { type: Function, default: undefined },
    },
    emits: ['show'],
    setup(props, { slots, emit, expose }) {
      const hide = vi.fn();
      const showPrevented = ref(false);
      expose({ hide, showPrevented });
      return () => {
        const prevented = showPrevented.value;
        return h(
          'div',
          {
            class: ['mock-tippy', prevented && 'show-prevented'],
            'data-show-prevented': prevented ? 'true' : undefined,
            onMouseenter: () => {
              const allowed = props.onShow?.() !== false;
              showPrevented.value = !allowed;
              emit('show');
            },
          },
          [slots.default?.(), slots.content?.()],
        );
      };
    },
  }),
  useTippy: vi.fn(),
}));

// Mock i18n
vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock common/constants
vi.mock('../../common/constants', () => ({
  CONST_MESSAGE_TOOLS: [
    { id: 'copy', name: '复制', description: '复制消息' },
    { id: 'regenerate', name: '重新生成', description: '重新生成回答' },
  ],
  CONST_UPDATE_TOOLS: [
    { id: 'like', name: '赞', description: '点赞' },
    { id: 'unlike', name: '踩', description: '点踩' },
  ],
}));

// Mock ToolBtn
vi.mock('../ai-buttons/tool-btn/tool-btn.vue', () => ({
  default: defineComponent({
    name: 'ToolBtn',
    props: {
      id: { type: String, default: '' },
      name: { type: String, default: '' },
      description: { type: String, default: '' },
      active: { type: Boolean, default: false },
      disabled: { type: Boolean, default: false },
      tippyOptions: { type: Object, default: undefined },
    },
    emits: ['click'],
    setup(props, { emit }) {
      return () =>
        h(
          'button',
          {
            class: ['mock-tool-btn', props.active && 'is-active', props.disabled && 'is-disabled'],
            'data-tool-id': props.id,
            'data-active': props.active,
            'data-disabled': props.disabled,
            'data-has-tippy-options': props.tippyOptions !== undefined ? 'true' : undefined,
            onClick: () => !props.disabled && emit('click'),
          },
          props.name,
        );
    },
  }),
}));

// Mock DeleteTool
vi.mock('./delete-tool/delete-tool.vue', () => ({
  default: defineComponent({
    name: 'DeleteTool',
    props: {
      id: { type: String, default: 'delete' },
      name: { type: String, default: '' },
      description: { type: String, default: '' },
      disabled: { type: Boolean, default: false },
      tippyOptions: { type: Object, default: undefined },
    },
    emits: ['confirm', 'cancel'],
    setup(props, { emit }) {
      return () =>
        h(
          'div',
          {
            class: ['mock-delete-tool', props.disabled && 'is-disabled'],
            'data-tool-id': props.id,
            'data-disabled': props.disabled,
          },
          [
            h('button', { class: 'delete-confirm-btn', onClick: () => emit('confirm') }, '删除'),
            h('button', { class: 'delete-cancel-btn', onClick: () => emit('cancel') }, '取消'),
          ],
        );
    },
  }),
}));

// Mock UserFeedback
vi.mock('./user-feedback/user-feedback.vue', () => ({
  default: defineComponent({
    name: 'UserFeedback',
    props: {
      loading: { type: Boolean, default: false },
      reasonList: { type: Array, default: () => [] },
      title: { type: String, default: '' },
    },
    emits: ['cancel', 'submit'],
    setup(_, { emit }) {
      return () =>
        h('div', { class: 'mock-user-feedback' }, [
          h('button', { class: 'feedback-cancel', onClick: () => emit('cancel') }, '取消'),
          h('button', { class: 'feedback-submit', onClick: () => emit('submit', ['reason1'], 'other') }, '提交'),
        ]);
    },
  }),
}));

describe('MessageTools', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(MessageTools);

      expect(wrapper.find('.ai-message-tools-container').exists()).toBe(true);
    });

    it('应该渲染默认的 messageTools', () => {
      wrapper = mount(MessageTools);

      const toolBtns = wrapper.findAll('.mock-tool-btn');
      expect(toolBtns.length).toBeGreaterThan(0);
    });

    it('应该渲染 updateTools', () => {
      wrapper = mount(MessageTools);

      // 默认有 like 和 unlike
      expect(wrapper.find('[data-tool-id="like"]').exists()).toBe(true);
      expect(wrapper.find('[data-tool-id="unlike"]').exists()).toBe(true);
    });

    it('有 updateTools 时应该渲染分隔线', () => {
      wrapper = mount(MessageTools);

      expect(wrapper.find('.ai-divider').exists()).toBe(true);
    });

    it('没有 updateTools 时不应该渲染分隔线', () => {
      wrapper = mount(MessageTools, {
        props: {
          updateTools: [],
        },
      });

      expect(wrapper.find('.ai-divider').exists()).toBe(false);
    });

    it('没有 updateTools 时不应该渲染右侧工具区', () => {
      wrapper = mount(MessageTools, {
        props: {
          updateTools: [],
        },
      });

      expect(wrapper.findAll('.message-tools').length).toBe(1);
    });
  });

  describe('两端插槽测试', () => {
    it('传入 prepend 插槽时应渲染在工具图标左侧的包裹容器内', () => {
      wrapper = mount(MessageTools, {
        slots: {
          prepend: '<span class="slot-time">12:00</span>',
        },
      });

      const prepend = wrapper.find('.ai-message-tools-prepend');
      expect(prepend.exists()).toBe(true);
      expect(prepend.find('.slot-time').exists()).toBe(true);
    });

    it('传入 append 插槽时应渲染在工具图标右侧的包裹容器内', () => {
      wrapper = mount(MessageTools, {
        slots: {
          append: '<span class="slot-time">12:00</span>',
        },
      });

      const append = wrapper.find('.ai-message-tools-append');
      expect(append.exists()).toBe(true);
      expect(append.find('.slot-time').exists()).toBe(true);
    });

    it('未传插槽时不应渲染两端包裹容器', () => {
      wrapper = mount(MessageTools);

      expect(wrapper.find('.ai-message-tools-prepend').exists()).toBe(false);
      expect(wrapper.find('.ai-message-tools-append').exists()).toBe(false);
    });
  });

  describe('Props 测试', () => {
    it('应该接收自定义 messageTools', () => {
      const customTools = [{ id: 'custom', name: '自定义', description: '自定义工具' }] as any[];

      wrapper = mount(MessageTools, {
        props: {
          messageTools: customTools,
        },
      });

      expect(wrapper.find('[data-tool-id="custom"]').exists()).toBe(true);
    });

    it('应该接收自定义 updateTools', () => {
      const customUpdateTools = [{ id: 'custom-update', name: '自定义更新', description: '自定义更新工具' }] as any[];

      wrapper = mount(MessageTools, {
        props: {
          updateTools: customUpdateTools,
        },
      });

      expect(wrapper.find('[data-tool-id="custom-update"]').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击工具按钮应该调用 onAction', async () => {
      const onAction = vi.fn();

      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'copy', name: '复制', description: '复制' }],
          updateTools: [],
          onAction,
        },
      });

      await wrapper.find('[data-tool-id="copy"]').trigger('click');

      expect(onAction).toHaveBeenCalled();
    });

    it('点击 like 按钮应该调用 onAction', async () => {
      const onAction = vi.fn().mockResolvedValue(['reason1', 'reason2']);

      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
          onAction,
        },
      });

      await wrapper.find('[data-tool-id="like"]').trigger('click');

      expect(onAction).toHaveBeenCalled();
    });

    it('UserFeedback 提交应该发出 feedback 事件', async () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
        },
      });

      // 点击提交按钮
      await wrapper.find('.feedback-submit').trigger('click');

      expect(wrapper.emitted('feedback')).toBeTruthy();
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 messageTools', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
        },
      });

      expect(wrapper.find('.ai-message-tools-container').exists()).toBe(true);
    });

    it('应该处理空的 updateTools', () => {
      wrapper = mount(MessageTools, {
        props: {
          updateTools: [],
        },
      });

      expect(wrapper.find('.ai-message-tools-container').exists()).toBe(true);
    });
  });

  describe('Active 状态测试', () => {
    it('提交反馈后 like 按钮应该变为 active 状态', async () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
        },
      });

      // 点击提交按钮
      await wrapper.find('.feedback-submit').trigger('click');

      // 验证 feedback 事件被触发
      expect(wrapper.emitted('feedback')).toBeTruthy();
    });

    it('like 和 unlike 按钮应该使用 Tippy 包裹', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [
            { id: 'like', name: '赞', description: '点赞' },
            { id: 'unlike', name: '踩', description: '点踩' },
          ],
        },
      });

      // 验证 Tippy 组件存在
      const tippyElements = wrapper.findAll('.mock-tippy');
      expect(tippyElements.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(MessageTools);

      expect(wrapper.find('.ai-message-tools-container').exists()).toBe(true);
      expect(wrapper.findAll('.message-tools').length).toBe(2);
    });

    it('工具栏按钮之间应使用 flex 布局排列', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [
            { id: 'copy', name: '复制', description: '复制' },
            { id: 'edit', name: '编辑', description: '编辑' },
          ],
          updateTools: [],
        },
      });

      const tools = wrapper.find('.message-tools');
      expect(tools.exists()).toBe(true);
      expect(wrapper.findAll('[data-tool-id]').length).toBe(2);
    });
  });

  describe('DeleteTool 测试', () => {
    it('messageTools 中 id 为 delete 的工具应渲染 DeleteTool 而非 ToolBtn', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'delete', name: '删除', description: '删除回答' }],
          updateTools: [],
        },
      });

      expect(wrapper.find('.mock-delete-tool').exists()).toBe(true);
      expect(wrapper.find('[data-tool-id="delete"].mock-tool-btn').exists()).toBe(false);
    });

    it('updateTools 中 id 为 delete 的工具也应渲染 DeleteTool', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'delete', name: '删除', description: '删除回答' }],
        },
      });

      expect(wrapper.find('.mock-delete-tool').exists()).toBe(true);
    });

    it('点击 DeleteTool 确认按钮应调用 onAction', async () => {
      const onAction = vi.fn().mockResolvedValue(undefined);

      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'delete', name: '删除', description: '删除回答' }],
          updateTools: [],
          onAction,
        },
      });

      await wrapper.find('.delete-confirm-btn').trigger('click');

      expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ id: 'delete' }));
    });

    it('messageToolsStatus 为 Disabled 时 DeleteTool 应被禁用', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'delete', name: '删除', description: '删除回答' }],
          updateTools: [],
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      const deleteTool = wrapper.find('.mock-delete-tool');
      expect(deleteTool.attributes('data-disabled')).toBe('true');
    });
  });

  describe('getTippyContent 测试', () => {
    it('like 按钮在未激活时应展示原始描述', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
        },
      });

      const toolBtn = wrapper.find('[data-tool-id="like"]');
      expect(toolBtn.exists()).toBe(true);
    });

    it('like 提交反馈后按钮 id 应变为 activeLike', async () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
        },
      });

      // 提交反馈后 submitId 会被设置为 'like'，getSubmitToolId 返回 'activeLike'
      await wrapper.find('.feedback-submit').trigger('click');
      await nextTick();

      const toolBtn = wrapper.find('[data-tool-id="activeLike"]');
      expect(toolBtn.exists()).toBe(true);
    });
  });

  describe('tippyOptions 测试', () => {
    it('应该正确接收 tippyOptions 属性', () => {
      const tippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageTools, {
        props: {
          tippyOptions,
        },
      });

      expect(wrapper.props().tippyOptions).toEqual(tippyOptions);
    });

    it('不传 tippyOptions 时组件应正常渲染', () => {
      wrapper = mount(MessageTools);

      expect(wrapper.find('.ai-message-tools-container').exists()).toBe(true);
      expect(wrapper.props().tippyOptions).toBeUndefined();
    });

    it('tippyOptions 应透传给 messageTools 中的 ToolBtn', () => {
      const tippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'copy', name: '复制', description: '复制' }],
          updateTools: [],
          tippyOptions,
        },
      });

      const toolBtn = wrapper.find('[data-tool-id="copy"]');
      expect(toolBtn.attributes('data-has-tippy-options')).toBe('true');
    });

    it('tippyOptions 应透传给 updateTools 中的 ToolBtn', () => {
      const tippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
          tippyOptions,
        },
      });

      const toolBtn = wrapper.find('[data-tool-id="like"]');
      expect(toolBtn.attributes('data-has-tippy-options')).toBe('true');
    });
  });

  describe('messageToolsStatus 测试', () => {
    it('应该正确接收 messageToolsStatus 属性', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      expect(wrapper.props().messageToolsStatus).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 为 Disabled 时，ToolBtn 应该被禁用', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'copy', name: '复制', description: '复制' }],
          updateTools: [],
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      const toolBtn = wrapper.find('[data-tool-id="copy"]');
      expect(toolBtn.attributes('data-disabled')).toBe('true');
      expect(toolBtn.classes()).toContain('is-disabled');
    });

    it('messageToolsStatus 为 Disabled 时，点击 ToolBtn 不应该调用 onAction', async () => {
      const onAction = vi.fn();

      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'copy', name: '复制', description: '复制' }],
          updateTools: [],
          messageToolsStatus: MessageToolsStatus.Disabled,
          onAction,
        },
      });

      await wrapper.find('[data-tool-id="copy"]').trigger('click');

      expect(onAction).not.toHaveBeenCalled();
    });

    it('messageToolsStatus 未设置时，ToolBtn 应该正常可用', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [{ id: 'copy', name: '复制', description: '复制' }],
          updateTools: [],
        },
      });

      const toolBtn = wrapper.find('[data-tool-id="copy"]');
      expect(toolBtn.attributes('data-disabled')).toBe('false');
      expect(toolBtn.classes()).not.toContain('is-disabled');
    });

    it('messageToolsStatus 为 Disabled 时，updateTools 中的按钮也应该被禁用', () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      const toolBtn = wrapper.find('[data-tool-id="like"]');
      expect(toolBtn.attributes('data-disabled')).toBe('true');
    });

    it('messageToolsStatus 为 Disabled 时，触发 Tippy show 应阻止展示（handleTippyShow 返回 false）', async () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [
            { id: 'like', name: '赞', description: '点赞' },
            { id: 'unlike', name: '踩', description: '点踩' },
          ],
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      const firstTippy = wrapper.find('.mock-tippy');
      await firstTippy.trigger('mouseenter');
      await nextTick();

      const tippyAfter = wrapper.find('.mock-tippy');
      expect(tippyAfter.attributes('data-show-prevented')).toBe('true');
      expect(tippyAfter.classes()).toContain('show-prevented');
    });

    it('messageToolsStatus 非 Disabled 时，触发 Tippy show 不应阻止展示', async () => {
      wrapper = mount(MessageTools, {
        props: {
          messageTools: [],
          updateTools: [{ id: 'like', name: '赞', description: '点赞' }],
          // 不传 messageToolsStatus，即非禁用状态
        },
      });

      const firstTippy = wrapper.find('.mock-tippy');
      await firstTippy.trigger('mouseenter');
      await nextTick();

      const tippyAfter = wrapper.find('.mock-tippy');
      expect(tippyAfter.attributes('data-show-prevented')).toBeUndefined();
      expect(tippyAfter.classes()).not.toContain('show-prevented');
    });
  });
});
