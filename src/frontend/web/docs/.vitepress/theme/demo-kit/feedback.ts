import type { FeedbackState, RunResult } from './types';

const REMOUNT_NOTE = '已按本配方配置重新挂载小鲸。';

/** 把 runtime.run 的结果转成舞台上的行内反馈；失败时统一引导到事件页签 */
export function resultFeedback<T>(result: RunResult<T>, onOk: (value: T | undefined) => FeedbackState): FeedbackState {
  if (!result.ok) return { kind: 'err', text: result.error || '执行失败', goto: 'events', gotoLabel: '查看事件' };
  const feedback = onOk(result.value);
  return result.remounted ? { ...feedback, text: `${REMOUNT_NOTE}${feedback.text}` } : feedback;
}
