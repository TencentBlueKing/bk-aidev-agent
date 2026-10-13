---
aside: false
---

# 侧栏 Tab 自定义

流程智能体（BKFlow）运行时，ChatBot 会在对话中渲染流程卡片，并在右侧侧栏提供「执行情况」Tab；点击节点的「详情」会打开该节点的详情 Tab。下面两个配方连接文档站内置的**巡检流程 Mock**（4 个节点，「磁盘检查」首次运行失败），事件格式与真实流程智能体一致。

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 执行情况与节点详情

<ClientOnly>
  <RecipeFlowRun />
</ClientOnly>

### SSE 事件序列

一次运行只通过 `chat_completion/` 的 SSE 推进，不轮询其他接口。所有 `flow_agent_*` 事件的 `value` 都是**任务数组**：

| 顺序 | 事件 | `value` 要点 |
| --- | --- | --- |
| 1 | `RUN_STARTED` | `threadId`、`runId` |
| 2 | `CUSTOM` `flow_agent_start` | `[{ task_id }]`，`task_id` 为数字；对话中新建流程卡片 |
| 3 | `CUSTOM` `flow_agent_result`（可多次） | `[{ task_id, task_name, task_state, nodes, statistics, task_outputs }]`；节点与任务状态为 BKFlow 大写（`RUNNING` / `FINISHED` / `FAILED` / `PENDING` / `SKIPPED` …） |
| 4 | `CUSTOM` `flow_agent_end` | `[{ task_id, task_outputs }]`；`task_outputs` 拼接为一条助手消息 |
| 5 | `RUN_FINISHED` | — |

```text
data: {"type":"CUSTOM","name":"flow_agent_start","value":[{"task_id":87748}]}
data: {"type":"CUSTOM","name":"flow_agent_result","value":[{"task_id":87748,"task_state":"FINISHED","nodes":{"nbd7…":{"id":"nbd7…","name":"消息展示","type":"ServiceActivity","state":"FINISHED","start_time":"2026-10-09 17:07:28 +0800","finish_time":"2026-10-09 17:07:28 +0800","elapsed_time":0,"loop":1,"retry":0,"skip":false,"retryable":true,"skippable":true}},"statistics":{"total":1,"state_counts":{"FINISHED":1}},"task_outputs":[""]}]}
data: {"type":"CUSTOM","name":"flow_agent_end","value":[{"task_id":87748,"task_outputs":[""]}]}
```

失败节点的「重试 / 跳过」：组件发送 `POST user_operation/`（`operation` 为 `flow_node_retry` / `flow_node_skip`，`payload: { node_id, task_id }`），随后自动新开 `chat_completion/`，后端以 `flow_agent_restart` 开始续跑同一个 `task_id`。节点详情 Tab 默认请求 `GET flow_agent/{task_id}/task_node_info/{node_id}/`。

## 自定义节点详情与 Tab 标签

<ClientOnly>
  <RecipeSideRenderCustom />
</ClientOnly>

::: tip 注意
- `getSideRenderComponent` 对**所有** Tab（含「执行情况」）都会调用，参数是 `tab.data.props`；不处理的 Tab 返回 `undefined` 才会走默认渲染。
- 侧栏会给你的组件注入 `locateButton` 插槽（「在对话中定位」），在组件里放 `<slot name="locateButton" />` 即可保留。
- 节点 Tab 的 `name` 为 `` `${task_id}|${node_id}|${node_name}` ``，`getSideTabRenderComponent` 可据此区分节点 Tab。
:::

## 相关文档

- [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization)：完整 API 与 AIBlueking 用法
- [ChatBot 组件 API](/api/ai-blueking/chatbot)
