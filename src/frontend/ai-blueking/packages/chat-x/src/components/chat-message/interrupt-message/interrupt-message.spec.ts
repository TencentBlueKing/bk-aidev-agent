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
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { APPROVAL_STATUS, InterruptReason } from '../../../ag-ui/types/constants';
import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
import InterruptMessage from './interrupt-message.vue';

import type {
  AIDevToolApprovalInterrupt,
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
    expect(wrapper.find('.ai-tool-approval-card__status').text()).toBe('评审中');
    expect(wrapper.text()).toContain('REV-2026-04-24-001');
    expect(wrapper.text()).toContain('2026-04-24 14:30:15');
    expect(wrapper.text()).toContain('张三、李四、王五');
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
    expect(wrapper.text()).toContain('当前处理人：无');
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
