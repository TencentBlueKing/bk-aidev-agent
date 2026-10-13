import type { ChatBotExpose } from '@blueking/ai-blueking';

// ① url 变化后 ChatBot 会重建内部实例：等新实例就绪后再读智能体信息
export async function waitAgentName(bot: ChatBotExpose): Promise<string | undefined> {
  await bot.whenReady();
  return bot.getChatHelper()?.agent.info.value?.agentName;
}

// 用法：<ChatBot :url="agentUrl" />，切换智能体只需改 agentUrl
