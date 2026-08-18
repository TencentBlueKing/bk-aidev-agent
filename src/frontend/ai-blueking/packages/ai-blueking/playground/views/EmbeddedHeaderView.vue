<template>
  <div class="embedded-header-view">
    <div class="view-header">
      <div class="view-header-row">
        <h2>嵌入模式业务 Header</h2>
        <SourceGuideDialog
          title="嵌入模式：接入说明与源码"
          :sections="embeddedHeaderGuideSections"
        />
      </div>
      <p class="view-desc">
        嵌入式 ChatBot 不自带 Header / 侧栏开关。业务方需自行放置会话名称，并用
        <code>v-model:asideCollapsed</code> 控制右侧侧栏。点击「查看源码」可复制最小接入代码。
      </p>
    </div>

    <div class="workbench">
      <aside class="session-panel">
        <button
          class="add-session-btn"
          type="button"
          :disabled="!chatHelperInstance"
          @click="createNewSession"
        >
          添加会话
        </button>
        <div class="session-list">
          <button
            v-for="session in sessionList"
            :key="session.sessionCode"
            type="button"
            class="session-item"
            :class="{ active: currentSession?.sessionCode === session.sessionCode }"
            @click="switchToSession(session.sessionCode)"
          >
            {{ session.sessionName }}
          </button>
          <p
            v-if="sessionList.length === 0"
            class="session-empty"
          >
            暂无会话
          </p>
        </div>
      </aside>

      <div class="chat-main">
        <header class="chat-main-header">
          <h1 class="chat-main-title">{{ currentSessionName }}</h1>
          <div class="chat-main-actions">
            <span
              class="aside-toggle"
              :title="asideCollapsed ? '展开侧栏' : '收起侧栏'"
              @click="asideCollapsed = !asideCollapsed"
            >
              <AsideToggleIcon />
            </span>
          </div>
        </header>
        <div class="chat-main-body">
          <ChatBot
            ref="chatBotRef"
            v-model:aside-collapsed="asideCollapsed"
            :url="apiUrl"
            height="100%"
            @agent-info-loaded="handleAgentInfoLoaded"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { cloneVNode, computed, defineComponent, ref, shallowRef, watch } from 'vue';

  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';
  import { CollapsedAsideIcon } from '@blueking/chat-x';

  import { embeddedHeaderGuideSections } from '../components/embedded-header-guide';
  import SourceGuideDialog from '../components/SourceGuideDialog.vue';

  type ChatHelper = NonNullable<ReturnType<ChatBotExpose['getChatHelper']>>;

  interface SessionItem {
    createdAt?: string;
    sessionCode: string;
    sessionName: string;
  }

  const AsideToggleIcon = defineComponent({
    name: 'AsideToggleIcon',
    setup() {
      return () => cloneVNode(CollapsedAsideIcon);
    },
  });

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const chatBotRef = ref<ChatBotExpose | null>(null);
  const chatHelperInstance = shallowRef<ChatHelper | null>(null);
  const asideCollapsed = ref(true);
  const sessionList = ref<SessionItem[]>([]);
  const currentSession = ref<SessionItem | null>(null);

  const currentSessionName = computed(() => currentSession.value?.sessionName?.trim() ?? '');

  const handleAgentInfoLoaded = (helper: ChatHelper) => {
    chatHelperInstance.value = helper;

    watch(
      () => helper.session.list.value,
      list => {
        sessionList.value = Array.isArray(list) ? ([...list] as SessionItem[]) : [];
      },
      { immediate: true, deep: true },
    );

    watch(
      () => helper.session.current?.value,
      current => {
        currentSession.value = (current as SessionItem) ?? null;
      },
      { immediate: true },
    );
  };

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
</script>

<style scoped>
  .view-header {
    margin-bottom: 16px;
  }

  .view-header-row {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .view-header h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .view-desc {
    margin: 0;
    font-size: 13px;
    line-height: 20px;
    color: #979ba5;
  }

  .view-desc code {
    padding: 0 4px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 2px;
  }

  .workbench {
    display: flex;
    height: calc(100vh - 160px);
    min-height: 480px;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .session-panel {
    display: flex;
    flex-direction: column;
    width: 240px;
    background: #f5f7fa;
    border-right: 1px solid #dcdee5;
  }

  .add-session-btn {
    height: 32px;
    margin: 12px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: #fff;
    border: 1px solid #3a84ff;
    border-radius: 2px;
  }

  .add-session-btn:disabled {
    color: #c4c6cc;
    cursor: not-allowed;
    border-color: #dcdee5;
  }

  .session-list {
    flex: 1;
    padding: 0 12px 12px;
    overflow-y: auto;
  }

  .session-item {
    display: block;
    width: 100%;
    padding: 10px 12px;
    margin-bottom: 8px;
    overflow: hidden;
    font-size: 12px;
    color: #4d4f56;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
    background: #fff;
    border: none;
    border-radius: 6px;
  }

  .session-item.active,
  .session-item:hover {
    color: #3a84ff;
    background: #e1ecff;
  }

  .session-empty {
    margin: 24px 0;
    font-size: 12px;
    color: #979ba5;
    text-align: center;
  }

  .chat-main {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .chat-main-header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 52px;
    padding: 0 16px 0 24px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
  }

  .chat-main-title {
    min-width: 0;
    margin: 0;
    overflow: hidden;
    font-size: 16px;
    font-weight: 400;
    line-height: 24px;
    color: #313238;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chat-main-actions {
    display: flex;
    flex-shrink: 0;
    align-items: center;
  }

  .aside-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    color: #63656e;
    cursor: pointer;
    border-radius: 2px;
  }

  .aside-toggle:hover {
    color: #4d4f56;
    background: #eaebf0;
  }

  .aside-toggle :deep(svg) {
    width: 14px;
    height: 14px;
  }

  .chat-main-body {
    flex: 1;
    min-height: 0;
  }

  .chat-main-body :deep(.ai-chatbot) {
    height: 100% !important;
  }
</style>
