import type { ChatBotExpose } from '@blueking/ai-blueking';

// ① 等初始化（智能体信息 + 会话列表）完成后再发送
export async function askWhenReady(bot: ChatBotExpose, text: string): Promise<void> {
  await bot.whenReady();
  await bot.sendMessage(text);
}

// ② 切换到指定会话（会加载该会话的历史消息）
export async function openSession(bot: ChatBotExpose, sessionCode: string): Promise<void> {
  await bot.whenReady();
  await bot.switchSession(sessionCode);
}
