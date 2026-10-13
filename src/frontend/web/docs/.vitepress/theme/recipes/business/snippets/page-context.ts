import { computed, type ComputedRef, type Ref } from 'vue';
import type { ChatBotExpose, IRequestOptions } from '@blueking/ai-blueking';

export interface ViewingTarget {
  bizId: number;
  host: string;
}

// ① 把用户正在查看的对象放进 context：会合并到每条消息的 property.extra.context
export function createContextRequestOptions(target: Ref<ViewingTarget>): ComputedRef<IRequestOptions> {
  return computed(() => ({
    context: { biz_id: target.value.bizId, host: target.value.host },
  }));
}

// ② 发送时无需再拼上下文：智能体从 property.extra.context 读取
export function askAboutTarget(bot: ChatBotExpose, question: string): Promise<void> {
  return bot.sendMessage(question);
}
