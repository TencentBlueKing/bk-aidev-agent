---
aside: false
---

# 请求参数与上下文

`requestOptions` 决定小鲸发出的每个请求带什么：`headers` 合并进请求头，`data` 对 GET 请求合并进 Query、对 POST / PUT / PATCH / DELETE 合并进 Body，`context` 合并进每条消息的 `property.extra.context`。它支持值、`ref` / `computed` 与函数，**依赖变化后，后续请求自动使用新值**，无需重建组件。

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 动态 Header 与参数

切换租户或轮换 token 后，再刷新会话列表（GET）或发送消息（POST），在请求页签对比 Header、Query 与 Body 的变化。

<ClientOnly>
  <RecipeTenantRequest />
</ClientOnly>

## 消息上下文 context

`context` 适合传「用户此刻在看什么」：它不会出现在用户看到的消息里，但会随消息一起交给智能体。Mock 回复的第一句会回显收到的上下文。

::: warning
2.4.x 只解析值形态的 `context`（对象或数组），函数形态会被静默忽略；像下面的片段一样把整个 `requestOptions` 写成 `computed` 即可。
:::

<ClientOnly>
  <RecipePageContext />
</ClientOnly>

## 相关文档

- [自定义请求](/guide/advanced-usage/custom-requests)：拦截器、`requestData` 与 `requestOptions` 的完整说明
- [快捷指令](/guide/core-features/shortcuts)：快捷指令表单字段同样写入 `property.extra.context`
