import { computed, type ComputedRef, type Ref } from 'vue';
import type { ChatBotExpose, IRequestOptions } from '@blueking/ai-blueking';

// ① 用 computed 组装 requestOptions：租户或 token 变化后，后续请求自动带上新值
export function createTenantRequestOptions(tenant: Ref<string>, token: Ref<string>): ComputedRef<IRequestOptions> {
  return computed(() => ({
    headers: { Authorization: `Bearer ${token.value}`, 'X-Tenant': tenant.value },
    // GET 请求合并进 query，POST 请求合并进 body
    data: { tenant_id: tenant.value },
  }));
}

// ② 刷新会话列表（GET session/）：tenant_id 出现在 query
export async function reloadSessions(bot: ChatBotExpose): Promise<number> {
  const helper = bot.getChatHelper();
  await helper?.session.getSessions();
  return helper?.session.list.value.length ?? 0;
}

// ③ 发送消息（POST session_content/）：tenant_id 出现在 body
export function ask(bot: ChatBotExpose, text: string): Promise<void> {
  return bot.sendMessage(text);
}

// 用法：<ChatBot :url="apiUrl" :request-options="requestOptions" />
