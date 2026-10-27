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
import { MessageRole, MessageStatus } from '../../../ag-ui/types/constants';
import {
  isMessageGenerating,
  resolveProcessCollapseIndex,
  resolveProcessLabelKey,
  shouldShowMessageProcess,
} from './message-process-status';

describe('message-process-status', () => {
  it('Streaming / StopLoading / Fetching / Pending 应该视为生成中', () => {
    expect(isMessageGenerating(MessageStatus.Streaming)).toBe(true);
    expect(isMessageGenerating(MessageStatus.StopLoading)).toBe(true);
    expect(isMessageGenerating(MessageStatus.Fetching)).toBe(true);
    expect(isMessageGenerating(MessageStatus.Pending)).toBe(true);
  });

  it('其余状态和空状态不应该视为生成中', () => {
    expect(isMessageGenerating(MessageStatus.Complete)).toBe(false);
    expect(isMessageGenerating(MessageStatus.Success)).toBe(false);
    expect(isMessageGenerating(MessageStatus.Error)).toBe(false);
    expect(isMessageGenerating(MessageStatus.Stop)).toBe(false);
    expect(isMessageGenerating(undefined)).toBe(false);
  });

  it('生成中应该显示处理中，终态文案应该看最后一条', () => {
    expect(resolveProcessLabelKey([{ status: MessageStatus.Complete }], true)).toBe('处理中');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Success }], false)).toBe('已完成');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Streaming }], false)).toBe('已完成');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Error }], false)).toBe('失败');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Stop }], false)).toBe('已停止');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Disabled }], false)).toBe('已禁用');
  });

  it('中途工具失败但最终正常完成时应显示已完成', () => {
    expect(
      resolveProcessLabelKey(
        [{ status: MessageStatus.Complete }, { status: MessageStatus.Error }, { status: MessageStatus.Complete }],
        false,
      ),
    ).toBe('已完成');
  });

  it('助手组只要有消息就显示状态栏，其他组不显示', () => {
    expect(shouldShowMessageProcess({ type: MessageRole.Assistant, messages: [{}] })).toBe(true);
    expect(shouldShowMessageProcess({ type: MessageRole.Assistant, messages: [{}, {}] })).toBe(true);
    expect(shouldShowMessageProcess({ type: MessageRole.Assistant, messages: [] })).toBe(false);
    expect(shouldShowMessageProcess({ type: MessageRole.User, messages: [{}] })).toBe(false);
    expect(shouldShowMessageProcess({ type: MessageRole.Loading, messages: [{}] })).toBe(false);
  });

  it('终态应该以最后一条 assistant 为折叠边界，生成中不折叠', () => {
    const messages = [
      { role: MessageRole.Assistant },
      { role: MessageRole.Reasoning },
      { role: MessageRole.Assistant },
      { role: MessageRole.Tool },
      { role: MessageRole.Info },
    ];

    expect(resolveProcessCollapseIndex(messages, false)).toBe(2);
    expect(resolveProcessCollapseIndex(messages, true)).toBe(0);
  });

  it('空组、没有 assistant 或最后一条 assistant 位于首位时不应折叠', () => {
    expect(resolveProcessCollapseIndex([], false)).toBe(0);
    expect(resolveProcessCollapseIndex([{ role: MessageRole.Assistant }], false)).toBe(0);
    expect(resolveProcessCollapseIndex([{ role: MessageRole.Reasoning }, { role: MessageRole.Info }], false)).toBe(0);
    expect(resolveProcessCollapseIndex([{ role: MessageRole.Assistant }, { role: MessageRole.Info }], false)).toBe(0);
  });
});
