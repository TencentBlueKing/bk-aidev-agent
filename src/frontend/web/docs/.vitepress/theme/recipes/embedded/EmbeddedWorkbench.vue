<template>
  <div class="workbench">
    <aside class="workbench__sessions">
      <button
        class="workbench__new"
        type="button"
        :disabled="!helper"
        @click="createSession"
      >
        ＋ 新建会话
      </button>
      <button
        v-for="session in sessions"
        :key="session.sessionCode"
        class="workbench__session"
        :class="{ 'is-active': session.sessionCode === current?.sessionCode }"
        type="button"
        @click="chooseSession(session.sessionCode)"
      >
        {{ session.sessionName || '未命名会话' }}
      </button>
    </aside>

    <section class="workbench__main">
      <header class="workbench__header">
        <span class="workbench__title">{{ current?.sessionName || '新会话' }}</span>
        <button
          class="workbench__toggle"
          type="button"
          :title="asideCollapsed ? '展开侧栏' : '收起侧栏'"
          @click="asideCollapsed = !asideCollapsed"
        >
          <AsideToggleIcon />
        </button>
      </header>
      <ChatBot
        ref="chatBot"
        v-model:aside-collapsed="asideCollapsed"
        v-bind="$attrs"
        height="100%"
        @agent-info-loaded="onAgentInfoLoaded"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
  import { cloneVNode, computed, defineComponent, ref, shallowRef } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';
  import { CollapsedAsideIcon } from '@blueking/chat-x';

  // url、requestOptions 等其余属性与事件透传给 ChatBot
  defineOptions({ inheritAttrs: false });

  type ChatHelper = NonNullable<ReturnType<ChatBotExpose['getChatHelper']>>;

  const AsideToggleIcon = defineComponent({ setup: () => () => cloneVNode(CollapsedAsideIcon) });

  const chatBot = ref<ChatBotExpose | null>(null);
  const helper = shallowRef<ChatHelper | null>(null);
  const asideCollapsed = ref(true);

  const sessions = computed(() => helper.value?.session.list.value ?? []);
  const current = computed(() => helper.value?.session.current.value ?? null);

  // ① 智能体信息加载完成后拿到 chatHelper：会话列表、当前会话都从这里读
  const onAgentInfoLoaded = (h: ChatHelper) => {
    helper.value = h;
  };

  // ② 切换会话：ChatBot 会自动加载该会话的消息
  const chooseSession = (sessionCode: string) => helper.value?.session.chooseSession(sessionCode);

  // ③ 新建会话并切换过去
  const createSession = () =>
    helper.value?.session.createSession({ sessionCode: `session_${Date.now()}`, sessionName: '新会话' });

  defineExpose({ chatBot });
</script>

<style scoped>
  .workbench {
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    grid-template-columns: 180px 1fr;
    height: 560px;
    overflow: hidden;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
  }

  .workbench__sessions {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px;
    overflow: auto;
    background: #fafbfd;
    border-right: 1px solid #f0f1f5;
  }

  .workbench__new {
    padding: 6px 10px;
    margin-bottom: 6px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: #fff;
    border: 1px dashed #a3c5fd;
    border-radius: 2px;
  }

  .workbench__new:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .workbench__session {
    padding: 7px 10px;
    overflow: hidden;
    font-size: 13px;
    color: #313238;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
    background: none;
    border: 0;
    border-radius: 4px;
  }

  .workbench__session:hover {
    background: #eef3fd;
  }

  .workbench__session.is-active {
    color: #3a84ff;
    background: #e1ecff;
  }

  .workbench__main {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  .workbench__header {
    display: flex;
    gap: 8px;
    align-items: center;
    height: 44px;
    padding: 0 14px;
    border-bottom: 1px solid #f0f1f5;
  }

  .workbench__title {
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .workbench__toggle {
    display: inline-flex;
    align-items: center;
    padding: 4px;
    margin-left: auto;
    font-size: 16px;
    color: #63656e;
    cursor: pointer;
    background: none;
    border: 0;
    border-radius: 2px;
  }

  .workbench__toggle:hover {
    background: #f0f1f5;
  }

  .workbench__main > :last-child {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
</style>
