import type { AIBluekingExpose, IShortcut } from '@blueking/ai-blueking';

import { scoped } from './scoped-request-options';

export function getCommand(ai: AIBluekingExpose): IShortcut {
  const command = ai.getChatHelper()?.agent.info.value?.conversationSettings?.commands?.[0];
  if (!command) throw new Error('当前智能体未配置快捷指令');
  return command;
}

export function prefill(cmd: IShortcut, sql: string, error: string): IShortcut {
  return {
    ...cmd,
    components: cmd.components.map(c => ({
      ...c,
      default: c.key === 'sql' ? sql : c.key === 'error' ? error : c.default,
    })),
  };
}

// ① 空表单：用户自己填写并提交
export async function openEmptyForm(ai: AIBluekingExpose): Promise<void> {
  await ai.show();
  ai.selectShortcut(getCommand(ai));
}

// ② 预填表单：用户确认或修改后提交
export async function openPrefilledForm(ai: AIBluekingExpose, sql: string, error: string): Promise<void> {
  await ai.show();
  ai.selectShortcut(prefill(getCommand(ai), sql, error));
}

// ③ 直接发送：跳过表单，并且只给这一次请求注入 Header
export async function sendDirectly(ai: AIBluekingExpose, sql: string, error: string): Promise<void> {
  await ai.show();
  await scoped.runWith({ headers: () => ({ set_ai_message: 'true' }) }, () =>
    ai.sendShortcut(prefill(getCommand(ai), sql, error), ''),
  );
}
