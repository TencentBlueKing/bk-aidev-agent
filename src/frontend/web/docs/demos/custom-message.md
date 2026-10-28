---
aside: false
---

# 消息自定义渲染

让智能体在回复中用 ```` ```custom-component ```` 代码块包裹一段 JSON，前端通过 `#message` 插槽接管消息渲染：`parseCustomBlocks` 把回复拆成文本块与自定义块，文本块交给 chat-x 的 `MessageRender`，自定义块按 `type` 分发到业务组件。系统提示词示例：

````text
当需要展示数据时，用以下格式输出图表：
```custom-component
{"type": "chart", "title": "近 7 天告警量", "data": {"labels": ["一", "二"], "values": [42, 38]}}
```
需要用户确认时输出表单：
```custom-component
{"type": "form", "title": "扩容确认", "fields": [{"label": "目标环境", "type": "select", "options": ["测试环境", "生产环境"]}], "actions": ["确认扩容", "取消"]}
```
````

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 图表、表单与嵌入页面

点击舞台上方的按钮让 Mock 返回带自定义块的回复。表单提交后，页面把结果作为一条新消息回传给智能体。

<ClientOnly>
  <RecipeCustomMessage />
</ClientOnly>

::: warning 当前行为
文档站示例使用已发布的 `3.1.0-beta.5`。`#message` 插槽会接管**全部**消息（包括用户消息），作用域只提供 `message`、`messageToolsStatus`、`onInterruptResume`。用户消息工具栏（复制 / 编辑 / 删除）所需的回调不在这个已发布包的作用域内。终态过程折叠时，插槽只收到当前可见的消息。
:::

## 代码块头部按钮

`#codeHeader` 插槽作用域为 `{ language, token }`：`token` 是该代码块对应的 markdown-it Token **数组**，代码原文取其中 `type === 'fence'`（或 `code_block`）那一项的 `content`。AIBlueking 与 ChatBot 都支持该插槽。

<ClientOnly>
  <RecipeCodeHeader />
</ClientOnly>

## 相关文档

- [消息自定义渲染指南](/guide/core-features/custom-message-rendering)：`parseCustomBlocks` 规则与更多组件类型
- [提示词与资源](/guide/core-features/prompts)：系统提示词与前端 prompts 的分工
