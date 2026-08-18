import type { SourceGuideSection } from './source-guide';

const MINIMAL_PAGE_CODE = `<template>
  <div class="chat-main">
    <header class="chat-main-header">
      <h1 class="chat-main-title">{{ currentSessionName }}</h1>
      <span
        class="aside-toggle"
        :title="asideCollapsed ? '展开侧栏' : '收起侧栏'"
        @click="asideCollapsed = !asideCollapsed"
      >
        <AsideToggleIcon />
      </span>
    </header>
    <ChatBot
      v-model:aside-collapsed="asideCollapsed"
      :url="apiUrl"
      height="100%"
      @agent-info-loaded="handleAgentInfoLoaded"
    />
  </div>
</template>

<script setup lang="ts">
  import { cloneVNode, computed, defineComponent, ref, shallowRef } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';
  import { CollapsedAsideIcon } from '@blueking/chat-x';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const AsideToggleIcon = defineComponent({
    name: 'AsideToggleIcon',
    setup() {
      return () => cloneVNode(CollapsedAsideIcon);
    },
  });

  type ChatHelper = NonNullable<ReturnType<ChatBotExpose['getChatHelper']>>;

  const apiUrl = '/api/';
  const chatHelperInstance = shallowRef<ChatHelper | null>(null);
  const asideCollapsed = ref(true);
  const currentSessionName = computed(
    () => chatHelperInstance.value?.session.current.value?.sessionName?.trim() ?? '',
  );

  const handleAgentInfoLoaded = (helper: ChatHelper) => {
    chatHelperInstance.value = helper;
  };
</script>

<style scoped>
  .chat-main {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    background: #fff;
  }
  .chat-main-header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 52px;
    padding: 0 16px 0 24px;
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
</style>
`;

export const embeddedHeaderGuideSections: SourceGuideSection[] = [
  {
    id: 'guide',
    label: '开发说明',
    notes: [
      'ChatBot 只有聊天区，不带 AIHeader。浮窗的展开/收起在 AIBlueking → AIHeader；嵌入页面必须业务自建 Header。',
      '左侧放当前会话名：@agent-info-loaded 拿到 chatHelper 后读 session.current.sessionName。chatHelper 用 shallowRef，避免内部 ref 被解包。',
      '右侧放展开/收起：必须 v-model:asideCollapsed。只写 :aside-collapsed 时，文件卡片 / addCustomTab 的内部展开会被丢掉。',
      '图标用 @blueking/chat-x 的 CollapsedAsideIcon。它是预创建 VNode，不能当 SFC 用，需 cloneVNode 包一层组件。',
      '侧栏固定从右侧展开，placement 已移除。',
      '本页左侧会话列表是演示用精简版。生产级（搜索、改名、批量删除）见 publish-template/src/views/ChatWindow.vue。',
    ],
  },
  {
    id: 'code',
    label: '接入源码',
    notes: [
      '本页完整实现：packages/ai-blueking/playground/views/EmbeddedHeaderView.vue',
      '生产级（会话搜索 / 改名 / 批量删除）：publish-template/src/views/ChatWindow.vue',
    ],
    blocks: [
      {
        title: '最小可复制页面',
        fileHint: 'YourEmbeddedChat.vue',
        desc: '拷到业务项目即可跑通 Header + 侧栏开关。会话列表按需自己接。',
        code: MINIMAL_PAGE_CODE,
      },
    ],
  },
];
