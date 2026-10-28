import type { ChatBotExpose } from '@blueking/ai-blueking';

// ① 流程智能体与普通智能体一样把 url 传给 ChatBot；对话中的流程卡片由 SSE 的 flow_agent_* 事件驱动，侧栏默认是「文件产物」
export function startInspection(bot: ChatBotExpose, host: string): Promise<void> {
  return bot.sendMessage(`开始巡检 ${host}`);
}

// ② 失败节点的「重试 / 跳过」在流程卡片上，由组件内置处理：POST user_operation/ 后自动新开 chat_completion 续流，无需业务代码

// ③ 关闭顶层折叠和过程状态栏：<ChatBot :url="flowAgentUrl" :enable-message-collapse="false" />
