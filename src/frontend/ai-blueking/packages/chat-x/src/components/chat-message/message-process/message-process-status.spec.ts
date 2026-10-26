import { MessageRole, MessageStatus } from '../../../ag-ui/types/constants';
import {
  canCollapseProcess,
  isMessageGenerating,
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

  it('非生成中且至少两条消息时才可折叠', () => {
    expect(canCollapseProcess([{}], false)).toBe(false);
    expect(canCollapseProcess([{}, {}], true)).toBe(false);
    expect(canCollapseProcess([{}, {}], false)).toBe(true);
  });
});
