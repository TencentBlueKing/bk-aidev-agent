import type { AIBluekingExpose } from '@blueking/ai-blueking';

// ① 新建一个具名会话并切换过去
export async function createNamedSession(ai: AIBluekingExpose, name: string): Promise<void> {
  await ai.show();
  await ai.addNewSession({ name });
}

// ② 修改当前会话的名称
export async function renameCurrent(ai: AIBluekingExpose, name: string): Promise<void> {
  const sessionCode = ai.getChatHelper()?.session.current.value?.sessionCode;
  if (!sessionCode) throw new Error('当前没有会话');
  await ai.updateSessionName(sessionCode, name);
}

// ③ 切换到指定会话
export async function switchTo(ai: AIBluekingExpose, sessionCode: string): Promise<void> {
  await ai.show();
  await ai.switchToSession(sessionCode);
}
