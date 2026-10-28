---
aside: false
---

# 错误处理与环境切换

AIBlueking 把初始化、会话、消息、分享等接口错误统一通过 `@sdk-error` 抛出，负载为 `{ apiName, code, message, data, source, action }`。默认还会弹出内置 toast；设置 `:error-toast="false"` 后由业务自行展示，`ignore-errors` 可按 URL 忽略指定接口的错误。

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 故障注入

选择一种故障后触发：文档站的 Mock 会根据请求头 `x-mock-fault` 返回对应错误。影响初始化的故障会先带着故障重新挂载右侧小鲸。

<ClientOnly>
  <RecipeFaultInjection />
</ClientOnly>

::: tip 观察要点
- 事件页签中 `@sdk-error` 的 `apiName` 区分了出错阶段（初始化 / 发送），业务可以据此给出不同提示。
- `@sdk-error` 的 `code` 恒为 `-1`；HTTP 状态码要从原始错误 `data.response.status` 读取（片段中的 `httpStatusOf`）。
- 打开请求页签可以看到故障头 `x-mock-fault` 与返回的状态码。
- 流中途的 `RUN_ERROR` 属于 AG-UI 协议事件，由协议层渲染为一条失败的助手消息，**不经过** `@sdk-error`；需要感知时监听 `receive-end` 并检查最后一条消息的状态。
:::

## 切换智能体 url

`url` 变化后，ChatBot 会销毁旧的内部实例并按新地址重新初始化；进行中的 `whenReady()` 会被 reject，切换后重新 `await whenReady()` 即可读取新智能体的信息。

<ClientOnly>
  <RecipeAgentSwitch />
</ClientOnly>

## 相关文档

- [编程式控制 · reportSdkError](/guide/advanced-usage/programmatic-control)：业务侧统一上报错误
- [多 Agent 切换](/guide/advanced-usage/multi-agent-switching)：多智能体场景的完整做法
