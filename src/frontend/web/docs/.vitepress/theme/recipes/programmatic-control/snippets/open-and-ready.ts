import type { AIBluekingExpose } from '@blueking/ai-blueking';

// ① 打开面板：await 结束即表示会话已就绪，可以安全读取会话信息
export async function openPanel(ai: AIBluekingExpose): Promise<string | undefined> {
  await ai.show();
  return ai.getChatHelper()?.session.current.value?.sessionName;
}

// ② 打开并切换到指定会话（切换发生在就绪之后）
export async function openSession(ai: AIBluekingExpose, sessionCode: string): Promise<void> {
  await ai.show(sessionCode);
}

// ③ 临时会话：打开后新建一个不进入历史列表的会话
export async function openTemporary(ai: AIBluekingExpose): Promise<void> {
  await ai.show();
  await ai.addNewSession({ name: '临时会话', isTemporary: true });
}

// ④ 关闭面板
export function closePanel(ai: AIBluekingExpose): void {
  ai.hide();
}
