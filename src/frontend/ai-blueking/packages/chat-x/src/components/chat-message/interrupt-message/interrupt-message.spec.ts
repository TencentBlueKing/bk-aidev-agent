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

import { type VueWrapper, mount } from '@vue/test-utils';
import { Button } from 'bkui-vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { APPROVAL_STATUS, InterruptReason } from '../../../ag-ui/types/constants';
import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
import InterruptMessage from './interrupt-message.vue';

import type {
  AIDevToolApprovalInterrupt,
  AIDevToolApprovalResume,
  Interrupt,
  UserQuestionAnswerItem,
  UserQuestionResume,
} from '../../../ag-ui/types/interrupt';

const copyMock = vi.fn();

vi.mock('vue-tippy', () => ({
  directive: {},
}));

vi.mock('../../../composables', () => ({
  useClipboard: () => ({
    copy: copyMock,
  }),
}));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const approvalInterrupt: AIDevToolApprovalInterrupt = {
  id: 'interrupt-1',
  reason: InterruptReason.AIDevToolApproval,
  toolCallId: 'tool-call-1',
  message: '需要关注技术评审单据',
  metadata: {
    ticket: {
      approvers: ['张三', '李四', '王五'],
      sn: 'REV-2026-04-24-001',
      status: APPROVAL_STATUS.PENDING,
      submit_time: '2026-04-24 14:30:15',
      title: '算法方案评审单',
      url: 'https://example.com/ticket/REV-2026-04-24-001',
    },
  },
};

const unsupportedInterrupt: Interrupt = {
  id: 'interrupt-2',
  reason: 'unknown_reason' as InterruptReason,
  toolCallId: 'tool-call-2',
  message: '暂不支持的中断消息',
};

const userQuestionAnswers: UserQuestionAnswerItem[] = [
  {
    question: '请选择语言',
    multiSelect: true,
    answer: [
      { label: 'Java', description: 'Java' },
      { label: 'others', description: 'Rust' },
    ],
  },
];

const userQuestionResume: UserQuestionResume = {
  interruptId: 'interrupt-user-question',
  reason: InterruptReason.UserQuestion,
  status: 'resolved',
  payload: {
    answers: userQuestionAnswers,
  },
};

const approvalResume: AIDevToolApprovalResume = {
  interruptId: 'interrupt-1',
  reason: InterruptReason.AIDevToolApproval,
  status: 'resolved',
  payload: {
    metadata: approvalInterrupt.metadata!,
  },
};

/** 与 message-render 透传一致：outcome / message 位于 content 内 */
const buildInterruptProps = (outcome: { interrupts?: Interrupt[]; type: string }, message?: string) => ({
  content: {
    message,
    outcome,
  },
});

describe('InterruptMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('open', vi.fn());
  });

  afterEach(() => {
    wrapper?.unmount();
    vi.unstubAllGlobals();
  });

  it('应该按设计稿渲染 AI Dev 工具审批单信息', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [approvalInterrupt],
      }),
    });

    expect(wrapper.find('.ai-interrupt-message').exists()).toBe(true);
    expect(wrapper.find('.ai-tool-approval-card__title').text()).toBe('算法方案评审单');
    expect(wrapper.find('.ai-tool-approval-card__status').text()).toBe('审批中');
    expect(wrapper.find('.ai-tool-approval-card__processor').exists()).toBe(true);
    expect(wrapper.text()).toContain('REV-2026-04-24-001');
    expect(wrapper.text()).toContain('2026-04-24 14:30:15');
    expect(wrapper.text()).toContain('张三、李四、王五');
    // 默认 fixture 无 toolArgs，不渲染参数区
    expect(wrapper.find('.ai-tool-approval-args').exists()).toBe(false);
  });

  it('存在 metadata.toolArgs 时应渲染工具参数，空对象不渲染', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [
          {
            ...approvalInterrupt,
            metadata: {
              ...approvalInterrupt.metadata!,
              toolArgs: { path: '/tmp/demo.py', force: true },
            },
          },
        ],
      }),
    });

    const args = wrapper.find('.ai-tool-approval-args');
    expect(args.exists()).toBe(true);
    expect(args.text()).toContain('参数');
    expect(args.text()).toContain('"path": "/tmp/demo.py"');
    expect(args.text()).toContain('"force": true');

    wrapper.unmount();
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [
          {
            ...approvalInterrupt,
            metadata: {
              ...approvalInterrupt.metadata!,
              toolArgs: {},
            },
          },
        ],
      }),
    });

    expect(wrapper.find('.ai-tool-approval-args').exists()).toBe(false);
  });

  it('revoked 状态应该显示已撤销并使用独立状态样式', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [
          {
            ...approvalInterrupt,
            metadata: {
              ticket: {
                ...approvalInterrupt.metadata?.ticket,
                approvers: [],
                status: APPROVAL_STATUS.REVOKED,
              },
            },
          },
        ],
      }),
    });

    const status = wrapper.find('.ai-tool-approval-card__status');
    expect(status.text()).toBe('已撤销');
    expect(status.classes()).toContain('ai-tool-approval-card__status--revoked');
    // 非 pending/draft 终态不展示当前处理人区域
    expect(wrapper.find('.ai-tool-approval-card__processor').exists()).toBe(false);
  });

  it('待审批状态点击取消审批应透传取消动作，不直接处理平台请求', async () => {
    const onInterruptResume = vi.fn();
    wrapper = mount(InterruptMessage, {
      props: {
        ...buildInterruptProps({
          type: 'interrupt',
          interrupts: [approvalInterrupt],
        }),
        onInterruptResume,
      },
    });

    await wrapper.find('.ai-tool-approval-card__cancel').trigger('click');

    expect(onInterruptResume).toHaveBeenCalledWith(
      {
        operation: InterruptResumeOperation.ApprovalCancel,
        payload: { interrupt_id: approvalInterrupt.id },
      },
      approvalInterrupt,
    );
  });

  it('点击取消审批后按钮进入 loading 并防重复提交', async () => {
    const onInterruptResume = vi.fn();
    wrapper = mount(InterruptMessage, {
      props: {
        ...buildInterruptProps({
          type: 'interrupt',
          interrupts: [approvalInterrupt],
        }),
        onInterruptResume,
      },
    });

    const cancelBtn = wrapper.find('.ai-tool-approval-card__cancel');
    await cancelBtn.trigger('click');
    await cancelBtn.trigger('click');

    expect(onInterruptResume).toHaveBeenCalledTimes(1);
    expect(cancelBtn.findComponent(Button).props('loading')).toBe(true);
  });

  it('审批中点击刷新图标透传刷新动作，2s 冷却内不可重复刷新', async () => {
    const onInterruptResume = vi.fn();
    wrapper = mount(InterruptMessage, {
      props: {
        ...buildInterruptProps({
          type: 'interrupt',
          interrupts: [approvalInterrupt],
        }),
        onInterruptResume,
      },
    });

    const refreshIcon = wrapper.find('.ai-tool-approval-card__refresh-icon');
    expect(refreshIcon.exists()).toBe(true);

    await refreshIcon.trigger('click');
    // 冷却中第二次点击不再触发
    await refreshIcon.trigger('click');

    expect(onInterruptResume).toHaveBeenCalledTimes(1);
    expect(onInterruptResume).toHaveBeenCalledWith(
      {
        operation: InterruptResumeOperation.ApprovalRefresh,
        payload: { interrupt_id: approvalInterrupt.id },
      },
      approvalInterrupt,
    );
  });

  it('终态不展示刷新图标', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [
          {
            ...approvalInterrupt,
            metadata: {
              ticket: { ...approvalInterrupt.metadata?.ticket, status: APPROVAL_STATUS.APPROVED },
            },
          },
        ],
      }),
    });

    expect(wrapper.find('.ai-tool-approval-card__refresh-icon').exists()).toBe(false);
  });

  it('终态应保留置灰的取消审批按钮，取消/撤销态文案为已取消审批', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [
          {
            ...approvalInterrupt,
            metadata: {
              ticket: { ...approvalInterrupt.metadata?.ticket, status: APPROVAL_STATUS.REJECTED },
            },
          },
        ],
      }),
    });

    const rejectBtn = wrapper.find('.ai-tool-approval-card__cancel');
    expect(rejectBtn.exists()).toBe(true);
    expect(rejectBtn.text()).toBe('取消审批');
    expect(rejectBtn.findComponent(Button).props('disabled')).toBe(true);

    wrapper.unmount();
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [
          {
            ...approvalInterrupt,
            metadata: {
              ticket: { ...approvalInterrupt.metadata?.ticket, status: APPROVAL_STATUS.CANCELLED },
            },
          },
        ],
      }),
    });

    expect(wrapper.find('.ai-tool-approval-card__cancel').text()).toBe('已取消审批');
  });

  it('点击查看单据详情时只打开单据链接，不触发 resume', async () => {
    const onInterruptResume = vi.fn();
    wrapper = mount(InterruptMessage, {
      props: {
        ...buildInterruptProps({
          type: 'interrupt',
          interrupts: [approvalInterrupt],
        }),
        onInterruptResume,
      },
    });

    await wrapper.find('.ai-tool-approval-card__detail').trigger('click');

    expect(window.open).toHaveBeenCalledWith('https://example.com/ticket/REV-2026-04-24-001', '_blank', 'noopener');
    expect(onInterruptResume).not.toHaveBeenCalled();
  });

  it('点击复制单据时复制单据链接，不触发 resume', async () => {
    const onInterruptResume = vi.fn();
    wrapper = mount(InterruptMessage, {
      props: {
        ...buildInterruptProps({
          type: 'interrupt',
          interrupts: [approvalInterrupt],
        }),
        onInterruptResume,
      },
    });

    await wrapper.find('.ai-tool-approval-card__copy-icon').trigger('click');

    expect(copyMock).toHaveBeenCalledWith('https://example.com/ticket/REV-2026-04-24-001');
    expect(onInterruptResume).not.toHaveBeenCalled();
  });

  it('不支持的中断类型应该显示兜底文案', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'interrupt',
        interrupts: [unsupportedInterrupt],
      }),
    });

    expect(wrapper.find('.ai-interrupt-message__fallback').exists()).toBe(true);
    expect(wrapper.text()).toContain('暂不支持的中断消息');
  });

  it('success outcome 不渲染中断卡片', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps({
        type: 'success',
      }),
    });

    expect(wrapper.find('.ai-tool-approval-card').exists()).toBe(false);
    expect(wrapper.find('.ai-interrupt-message__fallback').exists()).toBe(false);
  });

  it('success outcome 存在 UserQuestion resume 时应回显回答内容', () => {
    wrapper = mount(InterruptMessage, {
      props: {
        content: {
          outcome: { type: 'success' },
          result: userQuestionResume,
        },
      },
    });

    expect(wrapper.find('.ai-user-question-answered').exists()).toBe(true);
    expect(wrapper.text()).toContain('请选择语言');
    expect(wrapper.text()).toContain('Java');
    expect(wrapper.text()).toContain('Rust');
  });

  it('success outcome 存在 AIDevToolApproval resume 时应可交互回显审批单', async () => {
    const onInterruptResume = vi.fn();
    wrapper = mount(InterruptMessage, {
      props: {
        content: {
          outcome: { type: 'success' },
          result: approvalResume,
        },
        onInterruptResume,
      },
    });

    expect(wrapper.find('.ai-tool-approval-card').exists()).toBe(true);
    expect(wrapper.find('.ai-tool-approval-card__title').text()).toBe('算法方案评审单');
    expect(wrapper.text()).toContain('REV-2026-04-24-001');
    // readonly=false：回显审批单仍可交互，pending 态展示可点击的取消审批按钮与刷新图标
    expect(wrapper.find('.ai-tool-approval-card__refresh-icon').exists()).toBe(true);
    const cancelBtn = wrapper.find('.ai-tool-approval-card__cancel');
    expect(cancelBtn.exists()).toBe(true);

    // 回归：resultRenderers 须透传 onInterruptResume，否则取消点击调用次数为 0
    // interrupt 由 result.payload.metadata 还原
    await cancelBtn.trigger('click');
    expect(onInterruptResume).toHaveBeenCalledWith(
      { operation: InterruptResumeOperation.ApprovalCancel, payload: { interrupt_id: approvalResume.interruptId } },
      expect.objectContaining({ id: approvalResume.interruptId, reason: InterruptReason.AIDevToolApproval }),
    );
  });

  it('content.message 存在时应渲染提示文案', () => {
    wrapper = mount(InterruptMessage, {
      props: buildInterruptProps(
        {
          type: 'interrupt',
          interrupts: [approvalInterrupt],
        },
        '需要关注技术评审单据',
      ),
    });

    expect(wrapper.find('.ai-interrupt-message__content').text()).toBe('需要关注技术评审单据');
  });
});
