---
aside: false
---

# 写入输入框标签

`setInputContent` 用一份文档整篇替换输入框，不发送、不清掉已有引用。`ChatBot` 和 `AIBlueking` 是同一个方法；浮窗要先 `await show()`，再写入。文档站示例使用已发布的 `3.1.0-beta.6`。

字符串是纯文本。带标签时传入 `TagSchema`：二维数组，每一行是文本节点和标签节点。标签在输入框里显示成芯片，悬停展示 `description`。

::: warning 自定义类型必须自己的 Agent 支持
前端可以塞任意 `data.type`。发送时文档原样放进 `property.docSchema`。

官方 Agent 只认识 `tool`、`mcp`、`doc`、`knowledgebase`、`artifact`、`file`。`skill` 和 `shortcut` 会被忽略，不会当成资源挂上。其它类型（本页示例是 `host`）会报 **`docSchema tag type 非法`**。

`tool`、`skill` 也不是随便填一个名字就能用：`tool` 的 `value` 必须是已注册工具的 `code`，`skill` 不会进入官方装配。要让「生产服务器」这类业务标签生效，必须在自己的 Agent 里解析 `property.docSchema`，不能直接接到官方 Agent。

文档站 Mock 不校验标签类型，只用来看芯片。切到真实官方 Agent 后再发送，自定义类型会失败。
:::

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 写入标签、纯文本或清空

点「写入标签」后，输入框应出现「帮我分析」和一个「生产服务器」芯片，而不是纯文本 `@生产服务器`。

<ClientOnly>
  <RecipeSetInputContent />
</ClientOnly>

```ts
import type { ChatBotExpose } from '@blueking/ai-blueking';

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

function writeHostDoc(bot: ChatBotExpose) {
  bot.setInputContent(hostDoc());
}
```

`AIBlueking` 同样调用 `setInputContent`，只是先等面板打开：

```ts
await ai.show();
ai.setInputContent(hostDoc());
```

## 相关文档

- [提示词与资源 · 发送协议](/guide/core-features/prompts#发送协议propertydocschema)：官方标签类型与 `property.docSchema`
- [ChatBot Expose](/api/ai-blueking/chatbot#消息操作)
- [AIBlueking Expose](/api/ai-blueking/aiblueking#消息操作)
