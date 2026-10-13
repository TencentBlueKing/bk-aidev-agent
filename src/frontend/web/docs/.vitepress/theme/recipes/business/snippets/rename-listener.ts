import { ref, type Ref } from 'vue';
import type { ChatBotExpose } from '@blueking/ai-blueking';

// ① 业务侧按 sessionCode 维护会话名：首条消息后 AI 自动命名、或用户手动改名时触发 @rename
export function createSessionNameBook(): {
  names: Ref<Record<string, string>>;
  onRename: (newName: string, sessionCode: string) => void;
} {
  const names = ref<Record<string, string>>({});
  const onRename = (newName: string, sessionCode: string) => {
    names.value = { ...names.value, [sessionCode]: newName };
  };
  return { names, onRename };
}

// ② 发送消息：只有会话的第一条消息会触发自动命名
export function send(bot: ChatBotExpose, text: string): Promise<void> {
  return bot.sendMessage(text);
}

// ③ 新开一个会话：其第一条消息会再次触发 @rename
export async function startNewSession(bot: ChatBotExpose): Promise<void> {
  await bot.getChatHelper()?.session.createSession({ sessionCode: `session_${Date.now()}`, sessionName: '新会话' });
}

// 用法：<ChatBot :url="apiUrl" @rename="onRename" />
