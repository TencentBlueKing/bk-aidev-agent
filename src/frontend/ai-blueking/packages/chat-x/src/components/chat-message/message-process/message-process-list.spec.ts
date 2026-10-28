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
import { h } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { APPROVAL_STATUS, InterruptReason, MessageContentType, MessageRole, MessageStatus } from '../../../ag-ui/types/constants';
import MessageProcessList from './message-process-list.vue';

import type { ActivityMessage, AssistantMessage, InterruptMessage, Message } from '../../../ag-ui/types';

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const START = Date.parse('2026-01-01T00:00:00.000Z');

const createMessage = (id: string, content: string, status: MessageStatus, createdAt = START): AssistantMessage => ({
  id,
  content,
  createdAt,
  messageId: id,
  role: MessageRole.Assistant,
  status,
});

const flowMessage: ActivityMessage = {
  ...createMessage('flow', '', MessageStatus.Complete),
  role: MessageRole.Activity,
  activityType: MessageContentType.FlowAgent,
  content: [],
};
const approvalMessage: InterruptMessage = {
  ...createMessage('approval', '', MessageStatus.Complete),
  role: MessageRole.Interrupt,
  content: {
    outcome: {
      type: 'interrupt',
      interrupts: [{ id: 'approval-1', toolCallId: 'call-1', reason: InterruptReason.AIDevToolApproval }],
    },
  },
};

type MountOptions = {
  enableMessageCollapse?: boolean;
  enabled?: boolean;
  generating?: boolean;
  requestCreatedAt?: number | string;
};

describe('MessageProcessList', () => {
  const mountList = (
    messages: Message[],
    { enableMessageCollapse, enabled = true, generating = false, requestCreatedAt }: MountOptions = {},
  ) =>
    mount(MessageProcessList, {
      props: { enableMessageCollapse, enabled, generating, messages, requestCreatedAt },
      slots: {
        message: ({ message }: { message: Message }) =>
          h('div', { class: 'msg', 'data-message-id': message.id }, String(message.content)),
      },
    });

  it('终态后应该保留最后一条 assistant 及后续消息，点击后展开再收起', async () => {
    const wrapper = mountList(
      [
        createMessage('1', '过程一', MessageStatus.Complete, START + 1_000),
        createMessage('2', '过程二', MessageStatus.Complete, START + 60_000),
        createMessage('3', '最终回答', MessageStatus.Error, START + 122_000),
        {
          ...createMessage('4', '工具结果', MessageStatus.Complete, START + 122_000),
          role: MessageRole.Tool,
          toolCallId: 'call-1',
          duration: 0,
        },
        {
          ...createMessage('5', '补充提示', MessageStatus.Error, START + 122_000),
          role: MessageRole.Info,
        },
      ],
      { requestCreatedAt: START },
    );

    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['最终回答', '工具结果', '补充提示']);
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('失败，耗时 2m2s');

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual([
      '过程一',
      '过程二',
      '最终回答',
      '工具结果',
      '补充提示',
    ]);
    expect(wrapper.find('.ai-chevron-right-icon.is-expanded').exists()).toBe(true);

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['最终回答', '工具结果', '补充提示']);
    wrapper.unmount();
  });

  it('关闭顶层折叠应展示全部消息并隐藏状态栏和耗时，重新开启后恢复', async () => {
    const wrapper = mountList([
      createMessage('1', '前序过程', MessageStatus.Complete, START + 1_000),
      createMessage('2', '回答', MessageStatus.Complete, START + 8_000),
    ], { enableMessageCollapse: false, requestCreatedAt: START });

    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['前序过程', '回答']);
    expect(wrapper.find('.ai-message-process-header').exists()).toBe(false);

    await wrapper.setProps({ generating: true });
    expect(wrapper.find('.ai-message-process-header').exists()).toBe(false);
    await wrapper.setProps({ generating: false });
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    expect(wrapper.find('.ai-message-process-header').exists()).toBe(false);

    await wrapper.setProps({ enableMessageCollapse: true });
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['回答']);
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成，耗时 8s');
    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    await wrapper.setProps({ enableMessageCollapse: false });
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    expect(wrapper.find('.ai-message-process-header').exists()).toBe(false);
    await wrapper.setProps({ enableMessageCollapse: true });
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['回答']);
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成，耗时 8s');
    wrapper.unmount();
  });

  it('没有 assistant 时应该保留全部消息且不能折叠', async () => {
    const wrapper = mountList([
      { ...createMessage('1', '', MessageStatus.Complete), role: MessageRole.Reasoning, content: ['思考过程'] },
      { ...createMessage('2', '补充提示', MessageStatus.Complete), role: MessageRole.Info },
    ]);

    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['思考过程', '补充提示']);
    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    wrapper.unmount();
  });

  it('最后一条 assistant 位于首位时应该保留后续消息且不显示折叠箭头', async () => {
    const wrapper = mountList([
      createMessage('1', '回答', MessageStatus.Complete),
      { ...createMessage('2', '补充提示', MessageStatus.Complete), role: MessageRole.Info },
    ]);

    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['回答', '补充提示']);
    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    wrapper.unmount();
  });

  it('追加非 assistant 消息应直接展示，追加 assistant 后应更新折叠边界', async () => {
    const messages = [
      createMessage('1', '过程', MessageStatus.Complete),
      createMessage('2', '回答', MessageStatus.Complete),
    ];
    const wrapper = mountList(messages);
    const tip: Message = { ...createMessage('3', '补充提示', MessageStatus.Complete), role: MessageRole.Info };

    await wrapper.setProps({ messages: [...messages, tip] });
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['回答', '补充提示']);

    await wrapper.setProps({ messages: [...messages, tip, createMessage('4', '最新回答', MessageStatus.Complete)] });
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['最新回答']);
    wrapper.unmount();
  });

  it.each([
    { name: 'flow_agent', message: flowMessage },
    { name: '第三方审批', message: approvalMessage },
  ])('$name 及后续消息在生成结束、收起和追加回答后都应保持可见', async ({ message }) => {
    const messages = [
      createMessage('1', '前序过程', MessageStatus.Complete),
      message,
      createMessage('2', '回答', MessageStatus.Complete),
    ];
    const wrapper = mountList(messages, { generating: true });
    const visibleIds = () => wrapper.findAll('.msg').map(node => node.attributes('data-message-id'));

    expect(visibleIds()).toEqual(['1', message.id, '2']);
    await wrapper.setProps({ generating: false });
    expect(visibleIds()).toEqual([message.id, '2']);

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(visibleIds()).toEqual(['1', message.id, '2']);
    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(visibleIds()).toEqual([message.id, '2']);

    await wrapper.setProps({ messages: [...messages, createMessage('3', '后续回答', MessageStatus.Complete)] });
    expect(visibleIds()).toEqual([message.id, '2', '3']);
    wrapper.unmount();
  });

  it('特殊消息位于首位时应全部展示且没有折叠箭头', () => {
    const wrapper = mountList([flowMessage, createMessage('1', '回答', MessageStatus.Complete)]);

    expect(wrapper.findAll('.msg')).toHaveLength(2);
    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);
    wrapper.unmount();
  });

  it('审批从中断更新为已处理或已取消回显后仍应保持可见', async () => {
    const process = createMessage('1', '前序过程', MessageStatus.Complete);
    const answer = createMessage('2', '回答', MessageStatus.Complete);
    const wrapper = mountList([process, approvalMessage, answer]);

    for (const status of ['resolved', 'cancelled'] as const) {
      const content: InterruptMessage['content'] = {
        outcome: { type: 'success' },
        result: {
          interruptId: 'approval-1',
          reason: InterruptReason.AIDevToolApproval,
          status,
          payload: {
            metadata: {
              ticket: {
                approvers: [],
                sn: 'approval-1',
                status: status === 'resolved' ? APPROVAL_STATUS.APPROVED : APPROVAL_STATUS.CANCELLED,
                submit_time: '2026-01-01T00:00:00Z',
                title: '工具审批',
                url: 'https://example.com/approval-1',
              },
            },
          },
        },
      };
      await wrapper.setProps({ messages: [process, { ...approvalMessage, content }, answer] });

      expect(wrapper.findAll('.msg').map(node => node.attributes('data-message-id'))).toEqual(['approval', '2']);
    }
    wrapper.unmount();
  });

  it('生成中应该展示全部消息且不展示耗时，点击状态栏不折叠', async () => {
    const wrapper = mountList(
      [
        createMessage('1', '过程', MessageStatus.Complete, START),
        createMessage('2', '正在输出', MessageStatus.Complete, START + 5_000),
      ],
      { generating: true, requestCreatedAt: START },
    );

    expect(wrapper.findAll('.msg')).toHaveLength(2);
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('处理中');
    expect(wrapper.find('.ai-message-process-header-text').classes()).toContain('is-loading');
    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    wrapper.unmount();
  });

  it('生成结束后应该自动折叠前序过程，保留回答及后续消息并从用户提问时间算耗时', async () => {
    const wrapper = mountList(
      [
        createMessage('1', '过程', MessageStatus.Streaming, START + 2_000),
        createMessage('2', '正在输出', MessageStatus.Streaming, START + 5_000),
        { ...createMessage('3', '补充提示', MessageStatus.Complete, START + 6_000), role: MessageRole.Info },
      ],
      { generating: true, requestCreatedAt: START },
    );

    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('处理中');

    await wrapper.setProps({ generating: false });

    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['正在输出', '补充提示']);
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成，耗时 6s');

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg')).toHaveLength(3);
    await wrapper.setProps({ generating: true });
    expect(wrapper.findAll('.msg')).toHaveLength(3);
    await wrapper.setProps({ generating: false });
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['正在输出', '补充提示']);
    wrapper.unmount();
  });

  it('单条终态消息应该从用户提问时间算耗时，且不显示箭头', async () => {
    const wrapper = mountList([createMessage('1', '只有回答', MessageStatus.Complete, START + 65_000)], {
      requestCreatedAt: new Date(START).toISOString(),
    });

    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成，耗时 1m5s');
    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);
    expect(wrapper.findAll('.msg').map(node => node.text())).toEqual(['只有回答']);

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.findAll('.msg')).toHaveLength(1);
    wrapper.unmount();
  });

  it('createdAt 带毫秒时耗时应该舍去毫秒，只显示到秒', () => {
    const wrapper = mountList([createMessage('1', '回答', MessageStatus.Complete, START + 1_250)], {
      requestCreatedAt: '2026-01-01T00:00:00.000Z',
    });

    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成，耗时 1s');
    wrapper.unmount();
  });

  it('不足 1 秒显示 <1s，耗时为 0 时不显示耗时', async () => {
    const wrapper = mountList([createMessage('1', '回答', MessageStatus.Complete, START + 300)], {
      requestCreatedAt: START,
    });
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成，耗时 <1s');

    await wrapper.setProps({ messages: [createMessage('1', '回答', MessageStatus.Complete, START)] });
    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成');
    wrapper.unmount();
  });

  it('缺少用户提问时间时只显示状态，不显示耗时', () => {
    const wrapper = mountList([
      createMessage('1', '过程', MessageStatus.Complete, START),
      createMessage('2', '回答', MessageStatus.Complete, START + 5_000),
    ]);

    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('已完成');
    wrapper.unmount();
  });

  it('单条生成中消息应该显示处理中，不显示耗时', () => {
    const wrapper = mountList([createMessage('1', '正在输出', MessageStatus.Streaming, START + 5_000)], {
      generating: true,
      requestCreatedAt: START,
    });

    expect(wrapper.find('.ai-message-process-header-text').text()).toBe('处理中');
    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);
    wrapper.unmount();
  });

  it('未启用时不应该渲染状态栏', () => {
    const wrapper = mountList(
      [createMessage('1', '只有一条', MessageStatus.Complete), createMessage('2', '第二条', MessageStatus.Complete)],
      { enabled: false },
    );

    expect(wrapper.find('.ai-message-process-header').exists()).toBe(false);
    expect(wrapper.findAll('.msg')).toHaveLength(2);
    expect(wrapper.classes()).not.toContain('is-enabled');
    wrapper.unmount();
  });
});
