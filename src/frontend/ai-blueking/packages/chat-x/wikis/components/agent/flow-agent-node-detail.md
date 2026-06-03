---
name: FlowAgentNodeDetail FlowAgent 节点详情
slug: flow-agent-node-detail
kind: component
domain: agent
description: 展示 FlowAgent 节点输入、输出、异常、耗时等详情。
aiSummary: >
  展示 FlowAgent 节点输入、输出、异常、耗时等详情。
  源码位置：src/components/chat-content/flow-agent-content/flow-agent-node-detail.vue。
relatedComponents:
  - slug: flow-agent-content
    relation: 节点详情入口由 FlowAgentContent 挂载到自定义 Tab
  - slug: detail-section
    relation: 详情页内部分段容器
  - slug: simple-table
    relation: 展示输入参数、插件输出定义与结构化输出
  - slug: chat-container
    relation: 应用层通过 onCustomTabChange 拉取节点详情并回填
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import FlowAgentNodeDetailComp from '../../../src/components/chat-content/flow-agent-content/flow-agent-node-detail.vue';

  const nodeDetailData = {
    node_id: 'n1',
    task_id: 100,
    basic_info: {
      auto_retry: {
        enable: true,
        interval: 30,
        times: 2,
      },
      error_ignorable: false,
      node_name: '采集主机指标',
      optional: false,
      retryable: true,
      skippable: true,
      stage_name: '巡检准备',
      template_name: '主机巡检流程',
      timeout_config: {
        action: 'forced_fail',
        enable: true,
        seconds: 300,
      },
    },
    inputs: {
      bk_host_id: 10001,
      bk_cloud_id: 0,
      collect_items: ['cpu', 'memory', 'disk'],
      config: { interval: 60, timeout: 10 },
    },
    plugin_output: [
      {
        key: '${cpu_usage}',
        name: 'CPU 使用率',
        schema: {
          description: '当前主机 CPU 使用率',
          enum: [],
          type: 'number',
        },
        type: 'number',
      },
      {
        key: '${disk_usage}',
        name: '磁盘使用率',
        schema: {
          description: '根分区磁盘使用率',
          enum: [],
          type: 'number',
        },
        type: 'number',
      },
    ],
    outputs: [
      { key: 'cpu_usage', preset: false, value: 23.5 },
      { key: 'disk_usage', preset: false, value: { root: 71, data: 64 } },
    ],
  };

  const emptyNodeDetailData = {
    node_id: 'n2',
    task_id: 100,
    basic_info: {
      auto_retry: {
        enable: false,
        interval: 0,
        times: 0,
      },
      error_ignorable: false,
      node_name: '推送告警',
      optional: true,
      retryable: false,
      skippable: false,
      stage_name: '告警处理',
      template_name: '主机巡检流程',
      timeout_config: {
        action: '',
        enable: false,
        seconds: 0,
      },
    },
    inputs: {},
    plugin_output: [],
    outputs: [],
  };
</script>

# FlowAgentNodeDetail FlowAgent 节点详情

> **能力域**：Agent 能力

`FlowAgentNodeDetail` 用于展示 FlowAgent 单个节点的配置与输出详情。它通常被 `FlowAgentContent` 通过自定义 Tab 挂载到侧栏，应用层再根据 `messageUid`、`task_id`、`node_id` 拉取真实节点详情并回填到 `data`。

组件自身只负责详情展示，不负责接口请求、Tab 生命周期或消息定位逻辑。

## 源码事实

- **源码位置**：`src/components/chat-content/flow-agent-content/flow-agent-node-detail.vue`
- **能力说明**：展示 FlowAgent 节点输入、输出、异常、耗时等详情。

## 核心能力

- **双 Tab 展示**：内置“节点配置”和“节点输出”两个页签，默认展示“节点配置”
- **配置详情**：展示流程模板、节点名称、步骤名称、是否可选、失败处理和超时控制
- **参数表格**：使用 `SimpleTable` 展示输入参数、插件输出定义和结构化输出
- **加载骨架屏**：`loading` 为 `true` 时展示标题和内容骨架，不渲染真实数据
- **定位插槽**：提供 `locateButton` 插槽，允许侧栏注入“在对话中定位”等操作按钮
- **值格式化**：`null` / `undefined` 显示为 `--`，对象值通过 `JSON.stringify` 转为字符串

## 基础用法

```vue
<template>
  <FlowAgentNodeDetail
    :data="nodeDetailData"
    :loading="false"
    node_id="n1"
    node_name="采集主机指标"
    :task_id="100"
    task_name="主机巡检流程"
  >
    <template #locateButton>
      <button type="button">定位</button>
    </template>
  </FlowAgentNodeDetail>
</template>

<script setup lang="ts">
  import FlowAgentNodeDetail from '@blueking/chat-x/src/components/chat-content/flow-agent-content/flow-agent-node-detail.vue';
  import type { NodeDetailData } from '@blueking/chat-x';

  const nodeDetailData: Partial<NodeDetailData> = {
    basic_info: {
      node_name: '采集主机指标',
      template_name: '主机巡检流程',
      stage_name: '巡检准备',
      optional: false,
      skippable: true,
      retryable: true,
      error_ignorable: false,
      auto_retry: { enable: true, interval: 30, times: 2 },
      timeout_config: { enable: true, seconds: 300, action: 'forced_fail' },
    },
    inputs: {
      bk_host_id: 10001,
      collect_items: ['cpu', 'memory', 'disk'],
    },
    plugin_output: [
      {
        key: '${cpu_usage}',
        name: 'CPU 使用率',
        type: 'number',
        schema: { description: '当前主机 CPU 使用率', enum: [], type: 'number' },
      },
    ],
    outputs: [{ key: 'cpu_usage', preset: false, value: 23.5 }],
  };
</script>
```

**渲染效果**

<div class="demo" style="height: 520px; border: 1px solid #dcdee5;">
  <FlowAgentNodeDetailComp
    :data="nodeDetailData"
    :loading="false"
    node_id="n1"
    node_name="采集主机指标"
    :task_id="100"
    task_name="主机巡检流程"
  >
    <template #locateButton>
      <button
        style="height: 24px; padding: 0 10px; margin-left: auto; font-size: 12px; color: #3a84ff; cursor: pointer; background: #fff; border: 1px solid #3a84ff; border-radius: 2px;"
        type="button"
      >
        定位
      </button>
    </template>
  </FlowAgentNodeDetailComp>
</div>

## 加载态

`loading` 为 `true` 时，组件展示骨架屏，标题中的节点名和内容区均不会读取 `data` 展示。

<div class="demo" style="height: 360px; border: 1px solid #dcdee5;">
  <FlowAgentNodeDetailComp
    :data="{}"
    :loading="true"
    node_id="n1"
    node_name="采集主机指标"
    :task_id="100"
    task_name="主机巡检流程"
  />
</div>

## 空数据

当输入参数、插件输出定义或结构化输出为空时，对应 `SimpleTable` 渲染 `--` 占位行。

<div class="demo" style="height: 520px; border: 1px solid #dcdee5;">
  <FlowAgentNodeDetailComp
    :data="emptyNodeDetailData"
    :loading="false"
    node_id="n2"
    node_name="推送告警"
    :task_id="100"
    task_name="主机巡检流程"
  />
</div>

## Tab 内容

| Tab        | 内容                                                         |
| ---------- | ------------------------------------------------------------ |
| 节点配置   | 基础信息、失败处理、超时控制、输入参数、插件输出定义         |
| 节点输出   | 结构化输出，来自 `data.outputs`                              |

`activeTab` 是组件内部状态，不通过 prop 或 expose 暴露。

## 字段展示规则

| 区域         | 数据来源                         | 展示规则                                      |
| ------------ | -------------------------------- | --------------------------------------------- |
| 流程模板     | `data.basic_info.template_name`   | 空值显示 `--`                                 |
| 节点名称     | `data.basic_info.node_name`       | 空值显示 `--`                                 |
| 步骤名称     | `data.basic_info.stage_name`      | 空值显示 `--`                                 |
| 是否可选     | `data.basic_info.optional`        | `true` 显示“是”，否则显示“否”                 |
| 失败处理     | `skippable` / `auto_retry.enable` | 支持“手动跳过”和“自动重试”；均无时显示 `--`  |
| 超时控制     | `timeout_config`                  | 未启用时显示 `--`；`forced_fail` 显示“强制失败” |
| 输入参数     | `data.inputs`                     | 对象条目转为 `{ key, value }` 表格            |
| 插件输出定义 | `data.plugin_output`              | 展示名称、变量说明和 KEY                     |
| 结构化输出   | `data.outputs`                    | 展示输出 key 与格式化后的 value              |

## 自定义 Tab 联动

`FlowAgentContent` 点击节点“详情”时，会将本组件挂载到自定义 Tab，并先传入 `loading: true` 和节点定位参数：

```typescript
addCustomTab?.({
  label: node.name,
  name: `${task.task_id}|${node.id}|${node.name}`,
  data: {
    component: BkFlowNodeDetail,
    messageUid: props.messageUid,
    props: {
      loading: true,
      node_id: node.id,
      node_name: node.name,
      task_id: task.task_id,
      task_name: task.task_name,
      data: {},
    },
  },
});
```

应用层通常在 `ChatContainer` 的 `onCustomTabChange` 中读取这些参数，请求节点详情后返回新的 `props.data` 和 `props.loading`。

## API

### Props

| 属性名    | 类型                       | 必填 | 默认值 | 说明                         |
| --------- | -------------------------- | ---- | ------ | ---------------------------- |
| data      | `Partial<NodeDetailData>`  | 是   | —      | 节点详情数据                 |
| loading   | `boolean`                  | 否   | —      | 是否显示骨架屏               |
| node_id   | `string`                   | 否   | —      | 节点 ID，来自自定义 Tab 参数 |
| node_name | `string`                   | 否   | —      | 节点名称                     |
| task_id   | `number`                   | 否   | —      | 任务 ID                      |
| task_name | `string`                   | 否   | —      | 任务名称                     |

> Props 类型来自 `CustomBkFlowTabData['props'] & { data: Partial<NodeDetailData> }`。

### Emits

- 无。

### Slots

| 插槽名       | 说明                         |
| ------------ | ---------------------------- |
| locateButton | 标题栏右侧操作区，如定位按钮 |

### Expose

- 无。

## 类型定义

```typescript
export type CustomBkFlowTabData = CustomTabData<{
  data?: Partial<NodeDetailData>;
  loading?: boolean;
  node_id?: string;
  node_name?: string;
  task_id?: number;
  task_name?: string;
}>;

export interface NodeDetailData {
  inputs: Record<string, unknown>;
  node_id: string;
  task_id: number;
  basic_info: {
    auto_retry: {
      enable: boolean;
      interval: number;
      times: number;
    };
    error_ignorable: boolean;
    node_name: string;
    optional: boolean;
    retryable: boolean;
    skippable: boolean;
    stage_name: string;
    template_name: string;
    timeout_config: {
      action: string;
      enable: boolean;
      seconds: number;
    };
  };
  outputs: Array<{
    key: string;
    preset: boolean;
    value: unknown;
  }>;
  plugin_output: Array<{
    key: string;
    name: string;
    schema: {
      description: string;
      enum: unknown[];
      properties?: Record<string, unknown>;
      type: string;
    };
    type: string;
  }>;
}
```

## 使用建议

- 优先由 [FlowAgentContent](./flow-agent-content.md) 通过自定义 Tab 挂载，不建议业务组件手动拼装 Tab 生命周期。
- 接口请求与数据回填应放在应用层 `ChatContainer` 的 `onCustomTabChange` 链路中处理。
- `data` 可传 `Partial<NodeDetailData>`，但真实展示依赖 `basic_info`、`inputs`、`plugin_output`、`outputs` 等字段；缺字段时对应区域会降级为空表格或 `--`。

## 关联组件

- [FlowAgentContent](./flow-agent-content.md) — 节点详情入口。
- [DetailSection](./detail-section.md) — 详情分段容器。
- [SimpleTable](./simple-table.md) — 详情表格。
- [ChatContainer](../setup/chat-container.md) — 自定义 Tab 数据回填入口。
