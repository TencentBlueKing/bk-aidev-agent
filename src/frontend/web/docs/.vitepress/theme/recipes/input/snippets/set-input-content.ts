import type { ChatBotExpose } from '@blueking/ai-blueking';

/** 业务自定义标签。type 不是官方 Agent 认识的类型，发送给官方 Agent 会报错。 */
const hostDoc = () => [
  [
    { type: 'text' as const, text: '帮我分析 ' },
    {
      type: 'tag' as const,
      data: {
        description: '上海机房',
        icon: '',
        label: '生产服务器',
        type: 'host',
        value: 'host-001',
      },
    },
  ],
];

// ① 整篇替换输入框，不发送。标签按芯片显示，悬停可见 description
export function writeHostDoc(bot: ChatBotExpose): void {
  bot.setInputContent(hostDoc());
}

// ② 纯文本没有标签，不写 docSchema
export function writePlainText(bot: ChatBotExpose): void {
  bot.setInputContent('帮我看一下这台机器的负载');
}

// ③ 清空：传入一行空文档
export function clearInput(bot: ChatBotExpose): void {
  bot.setInputContent([[]]);
}
