---
name: UserFeedback 用户反馈
slug: user-feedback
kind: component
domain: feedback
description: 用户反馈弹层，提交踩/反馈原因。
aiSummary: >
  用户反馈弹层，提交踩/反馈原因。
  源码位置：src/components/message-tools/user-feedback/user-feedback.vue。
relatedComponents:
  - slug: message-tools
    relation: 点赞/踩操作触发并收集反馈
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { shallowRef } from 'vue';
  import UserFeedbackComp from '../../../src/components/message-tools/user-feedback/user-feedback.vue'

  const positiveReasons = ['回答准确', '信息全面', '表达清晰', '解决了问题', '示例恰当'];
  const negativeReasons = ['信息错误', '回答不相关', '解释不清楚', '没有解决问题', '内容不完整', '格式混乱'];

  const isLoading = shallowRef(true);

  const handleSubmit = (selectedReasons, otherReason) => {
    console.log('已选原因:', selectedReasons, '补充说明:', otherReason);
  };

  const handleCancel = () => {
    console.log('取消反馈');
  };
</script>

# MessageUserFeedback 用户反馈
## 源码事实

- **源码位置**：`src/components/message-tools/user-feedback/user-feedback.vue`
- **能力域**：工具与反馈
- **能力说明**：用户反馈弹层，提交踩/反馈原因。



> **能力域**：工具与反馈

AI 消息点赞/踩后收集用户具体反馈原因的弹出面板。支持多选预设原因标签、补充文字说明（textarea）、异步加载原因列表（骨架屏）。

> **通常不需要直接使用。** `MessageTools` 在用户点击 `like`/`unlike` 工具按钮时，会通过内置 Tippy 弹出层自动呈现本组件，并驱动 `loading` 和 `reasonList`。

## 组件结构

```
.ai-user-feedback（width: 400px，padding: 16px，gap: 16px）
├── .ai-feedback-title（font-size: 16px，color: #313238）
│     props.title
│
├── .ai-feedback-reason-list（flex-wrap，gap: 4px）
│     loading=true  → 8 × .reason-item.ai-skeleton-element（每项 width: 70px）
│     loading=false → v-for reasonList → .reason-item
│                       is-active（已选）：color #1768ef，bg #e1ecff
│                       :hover        ：同上（与 is-active 共享样式）
│
├── .ai-feedback-other
│     bkui-vue Input（type=textarea，rows=3，placeholder="说出您的想法"）
│     → v-model 绑定内部 shallowRef otherReason
│
└── .ai-feedback-footer（justify-content: flex-end，gap: 8px）
      Button primary "提交"（width: 64px，disabled：selectedReasons 空且 otherReason 空）
      Button default "取消"（width: 64px）
```

## 基础用法

```vue
<template>
  <MessageUserFeedback
    title="什么原因让你满意？"
    :reason-list="reasonList"
    @submit="handleSubmit"
    @cancel="handleCancel"
  />
</template>

<script setup lang="ts">
  import { MessageUserFeedback } from '@blueking/chat-x';

  const reasonList = ['回答准确', '信息全面', '表达清晰', '解决了问题', '示例恰当'];

  const handleSubmit = (selectedReasons: string[], otherReason: string) => {
    // selectedReasons: 当前已勾选的原因（提交后组件不自动清空）
    // otherReason: textarea 中的补充说明（可为空字符串）
    console.log('已选原因:', selectedReasons, '补充说明:', otherReason);
  };

  const handleCancel = () => {
    // cancel 触发前组件已清空 selectedReasons 和 otherReason
    console.log('用户取消了反馈');
  };
</script>
```

**满意反馈**

<div class="demo">
  <UserFeedbackComp
    title="什么原因让你满意？"
    :reason-list="positiveReasons"
    @submit="handleSubmit"
    @cancel="handleCancel"
  />
</div>

**不满意反馈**

<div class="demo">
  <UserFeedbackComp
    title="什么原因让你不满意？"
    :reason-list="negativeReasons"
    @submit="handleSubmit"
    @cancel="handleCancel"
  />
</div>

## 加载状态

原因列表通常需要异步获取，将 `loading` 设为 `true` 时渲染 **8 个**骨架屏占位块（固定数量，与 `reasonList` 无关），数据就绪后切换为 `false`：

```vue
<template>
  <MessageUserFeedback
    title="什么原因让你满意？"
    :reason-list="reasonList"
    :loading="isLoading"
    @submit="handleSubmit"
    @cancel="handleCancel"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageUserFeedback } from '@blueking/chat-x';

  const isLoading = ref(true);
  const reasonList = ref<string[]>([]);

  async function fetchReasons() {
    isLoading.value = true;
    try {
      reasonList.value = await fetchFeedbackReasons();
    } finally {
      isLoading.value = false;
    }
  }
</script>
```

**骨架屏效果**

<div class="demo">
  <UserFeedbackComp
    title="什么原因让你满意？"
    :reason-list="[]"
    :loading="isLoading"
    @submit="handleSubmit"
    @cancel="handleCancel"
  />
</div>

## 交互说明

| 操作         | 行为说明                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------- |
| 点击原因标签 | **多选**，高亮（`is-active`）；再次点击取消选中；hover 效果与选中态相同                                       |
| 填写补充说明 | 可选；不选任何标签时，仅有补充说明文本也可解锁提交按钮                                                        |
| 点击提交     | `selectedReasons.length === 0 && otherReason === ''` 时禁用；点击后触发 `submit` 事件，**组件不自动清空状态** |
| 点击取消     | 先将 `selectedReasons` 和 `otherReason` 清空（两者均重置），再触发 `cancel` 事件                              |

> **提交与取消的状态差异**：点击"提交"后内部 `selectedReasons` / `otherReason` **不重置**，由父组件决定后续行为（如关闭弹层）；点击"取消"则**立即重置**两者，再触发事件。

## 与 MessageTools 配合使用

`MessageUserFeedback` 在实际场景中由 `MessageTools` 驱动，整体流程：

```
用户点击 like / unlike
    ↓
MessageTools 内部：loading=true，弹出反馈面板（骨架屏）
    ↓
调用 onAction(tool) → 返回 string[]（支持 async）
    ↓
loading=false，展示原因标签列表
    ↓
用户选择原因 → 点击提交
    ↓
触发 onAgentFeedback(tool, messages, reasonList, otherReason)
```

```vue
<template>
  <MessageContainer
    :messages="messages"
    :on-agent-action="handleAgentAction"
    :on-agent-feedback="handleFeedback"
  />
</template>

<script setup lang="ts">
  import { MessageContainer, type IToolBtn, type Message } from '@blueking/chat-x';

  const messages: Message[] = [
    /* ... */
  ];

  // 点击 like/unlike 时调用，返回原因列表（支持异步）
  const handleAgentAction = async (tool: IToolBtn): Promise<string[]> => {
    if (tool.id === 'like') {
      return ['回答准确', '信息全面', '表达清晰', '解决了问题'];
    }
    if (tool.id === 'unlike') {
      return ['信息错误', '回答不相关', '解释不清楚', '没有解决问题'];
    }
    return [];
  };

  // 用户提交反馈后触发
  const handleFeedback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => {
    console.log(`${tool.id} 反馈:`, { reasonList, otherReason });
    // 上报到后端
  };
</script>
```

若需在自定义位置独立使用，可配合 `vue-tippy`：

```vue
<template>
  <Tippy
    :arrow="false"
    interactive
    trigger="click"
    theme="ai-chat-box-light light"
    :offset="[0, 6]"
    :append-to="() => document.body"
  >
    <button>👍 点赞</button>
    <template #content>
      <MessageUserFeedback
        title="什么原因让你满意？"
        :reason-list="reasonList"
        :loading="isLoading"
        @submit="handleSubmit"
        @cancel="handleCancel"
      />
    </template>
  </Tippy>
</template>
```

## API

### Props

| 属性名     | 类型       | 必填 | 默认值  | 说明                                                   |
| ---------- | ---------- | ---- | ------- | ------------------------------------------------------ |
| title      | `string`   | ✓    | —       | 面板标题文本                                           |
| reasonList | `string[]` | ✓    | —       | 预设原因标签列表；`loading=true` 时列表不渲染          |
| loading    | `boolean`  | —    | `false` | `true` 时显示 8 个骨架屏占位块，隐藏 `reasonList` 内容 |

### Events

| 事件名 | 参数签名                                      | 触发时机                                                    |
| ------ | --------------------------------------------- | ----------------------------------------------------------- |
| submit | `(reasonList: string[], otherReason: string)` | 点击提交按钮时（至少一项原因或补充说明不为空）              |
| cancel | —                                             | 点击取消按钮时（内部已重置 selectedReasons 和 otherReason） |

### 内部状态

以下为组件内部 `shallowRef` 状态，不暴露为 props/emits：

| 状态名          | 类型       | 说明                                        |
| --------------- | ---------- | ------------------------------------------- |
| selectedReasons | `string[]` | 当前已选原因列表；取消时重置，提交时不重置  |
| otherReason     | `string`   | textarea 补充说明；取消时重置，提交时不重置 |

## 关联组件

- [MessageTools](/components/feedback/message-tools) — 点赞/踩入口与反馈联动
