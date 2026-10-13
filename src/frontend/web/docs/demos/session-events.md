---
aside: false
---

# 会话与事件

会话的**第一条消息**发出后，小鲸会让 AI 自动命名并触发 `@rename(newName, sessionCode)`；业务如果自己维护会话列表，按 `sessionCode` 同步即可。通过 `updateSessionName` 编程式改名**不会**触发 `@rename`，调用方在 `await` 之后自行同步。

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 首条消息后自动命名

<ClientOnly>
  <RecipeAutoRename />
</ClientOnly>

## 手动重命名与切换

AIBlueking 的 `addNewSession` / `updateSessionName` / `switchToSession` 可以从业务页直接管理会话，例如每个工单对应一个会话。

<ClientOnly>
  <RecipeSessionControl />
</ClientOnly>

## 相关文档

- [会话管理](/guide/core-features/session-management)：会话生命周期、临时会话、会话列表
- [自定义会话列表](/guide/advanced-usage/external-session-list)：在业务侧完整渲染会话列表
