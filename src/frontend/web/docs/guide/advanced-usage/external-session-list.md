# 自定义会话列表

本文介绍如何构建一个带有**左侧会话列表 + 右侧 ChatBot** 的完整聊天页面，实现外部会话列表与 ChatBot 的联动。

::: tip 适用场景
当 AIBlueking 内置的会话管理 UI 无法满足需求时（如需要搜索过滤、批量操作、自定义样式等），可以使用本方案构建完全自定义的会话列表。
:::

## 核心思路

1. 使用 `ChatBot` 组件处理核心聊天逻辑
2. 通过 `@agent-info-loaded` 事件获取 `chatHelper` 实例
3. 监听 `chatHelper.session.list` 和 `chatHelper.session.current` 获取响应式会话数据
4. 通过 `chatHelper.session` 的方法（`chooseSession`、`createSession`、`deleteSession` 等）操作会话

## 精简示例

```vue
<template>
  <div class="chat-window">
    <!-- 左侧会话列表 -->
    <aside class="session-panel">
      <input v-model="searchQuery" placeholder="搜索会话名称" />
      <button @click="createNewSession">添加会话</button>

      <div class="session-list">
        <div
          v-for="session in filteredSessionList"
          :key="session.sessionCode"
          :class="['session-item', { active: currentSession?.sessionCode === session.sessionCode }]"
          @click="switchToSession(session.sessionCode)"
        >
          <span class="session-name">{{ session.sessionName }}</span>
          <span class="session-actions">
            <button @click.stop="renameByAI(session.sessionCode)">AI 命名</button>
            <button @click.stop="deleteSingle(session.sessionCode)">删除</button>
          </span>
        </div>
      </div>
    </aside>

    <!-- 右侧聊天区域 -->
    <main class="chat-main">
      <ChatBot
        ref="chatBotRef"
        :url="url"
        height="100%"
        @agent-info-loaded="handleAgentInfoLoaded"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, computed, watch } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';

type ChatHelper = NonNullable<ReturnType<ChatBotExpose['getChatHelper']>>;

const chatBotRef = ref<ChatBotExpose | null>(null);
// 重点：使用 shallowRef 存储 chatHelper，避免 reactive 自动解包内部 ref
const chatHelperInstance = shallowRef<ChatHelper | null>(null);
const searchQuery = ref('');
const sessionList = ref<any[]>([]);
const currentSession = ref<any | null>(null);
const url = ref('https://your-aidev-url.com/api/');

// 搜索过滤
const filteredSessionList = computed(() => {
  if (!searchQuery.value) return sessionList.value;
  const query = searchQuery.value.toLowerCase();
  return sessionList.value.filter(s => s.sessionName.toLowerCase().includes(query));
});

// 核心：通过 @agent-info-loaded 获取 chatHelper 实例
const handleAgentInfoLoaded = (helper: ChatHelper) => {
  chatHelperInstance.value = helper;

  // 监听会话列表变化
  watch(
    () => helper.session.list.value,
    (list) => {
      sessionList.value = Array.isArray(list) ? [...list] : [];
    },
    { immediate: true, deep: true },
  );

  // 监听当前会话变化
  watch(
    () => helper.session.current?.value,
    (current) => {
      currentSession.value = current ?? null;
    },
    { immediate: true },
  );
};

// 会话操作
const switchToSession = async (sessionCode: string) => {
  if (!chatHelperInstance.value) return;
  await chatHelperInstance.value.session.chooseSession(sessionCode);
};

const createNewSession = async () => {
  if (!chatHelperInstance.value) return;
  await chatHelperInstance.value.session.createSession({
    sessionCode: `new_session_${Date.now()}`,
    sessionName: '新会话',
  });
};

const deleteSingle = async (sessionCode: string) => {
  if (!chatHelperInstance.value) return;
  await chatHelperInstance.value.session.deleteSession(sessionCode);
};

const renameByAI = async (sessionCode: string) => {
  if (!chatHelperInstance.value) return;
  await chatHelperInstance.value.session.renameSession(sessionCode);
};
</script>

<style scoped>
.chat-window {
  display: flex;
  width: 100%;
  height: 100vh;
}
.session-panel {
  width: 300px;
  border-right: 1px solid #dcdee5;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.session-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.session-item:hover { background-color: #f0f5ff; }
.session-item.active { background-color: #e1ecff; color: #3a84ff; }
.session-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-main { flex: 1; min-width: 0; }
</style>
```

## 关键要点

### 1. 使用 `shallowRef` 存储 chatHelper

```ts
const chatHelperInstance = shallowRef<ChatHelper | null>(null);
```

`chatHelper` 内部包含多个 `ref` 属性（如 `session.list`、`session.current`），使用 `shallowRef` 可以避免 Vue 的 `reactive` 自动解包这些内部 ref，保留其原始语义。

### 2. 通过 `@agent-info-loaded` 获取实例

```ts
const handleAgentInfoLoaded = (helper: ChatHelper) => {
  chatHelperInstance.value = helper;
  // 此时可以访问所有会话管理 API
};
```

该事件在 ChatBot 完成 Agent 信息加载后触发，此时 `chatHelper` 已完全初始化。

### 3. 响应式会话数据

```ts
watch(() => helper.session.list.value, (list) => {
  sessionList.value = [...list];
}, { immediate: true, deep: true });
```

`helper.session.list` 和 `helper.session.current` 是响应式的 `Ref`，任何会话操作（创建、删除、切换）都会自动更新。

### 4. 会话操作 API

| 方法 | 说明 |
|------|------|
| `session.chooseSession(code)` | 切换到指定会话 |
| `session.createSession(options)` | 创建新会话 |
| `session.deleteSession(code)` | 删除指定会话 |
| `session.renameSession(code)` | AI 自动生成会话标题 |
| `session.updateSession(session)` | 更新会话信息（如手动重命名） |

## 进阶：批量操作、编辑标题

完整的生产级实现可参考 `publish-template/src/views/ChatWindow.vue`，该文件包含：

- 搜索过滤会话
- 内联编辑会话标题
- AI 自动生成标题
- 勾选 + 批量删除
- 删除确认弹窗
- Loading 状态管理
- 错误处理与 403 跳转

> 实际项目中建议基于 `ChatWindow.vue` 进行修改，而非从零开始编写。
