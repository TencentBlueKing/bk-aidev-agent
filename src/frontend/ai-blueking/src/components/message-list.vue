<template>
  <div
    ref="messageWrapper"
    :style="{ opacity: hasSessionContents ? 1 : 0 }"
    class="message-wrapper"
  >
    <div
      v-for="(message, index) in sessionContents"
      :key="message.id"
      class="message-line-wrapper"
    >
      <render-message
        :index="index"
        :message="message"
        :is-select-mode="isSelectMode"
        :is-message-selected="isMessageSelected"
        :last-message-id="index === 0 ? undefined : getMessageId(index - 1)"
        @delete="handleDelete"
        @regenerate="handleRegenerate"
        @resend="handleResend"
        @message-select="handleMessageSelect"
        @update-session-content="handleUpdateSessionContent"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import type { ISessionContent } from '@blueking/ai-ui-sdk/types';
  import { ref, onMounted, onBeforeUnmount } from 'vue';

  import renderMessage from './render-message.vue';

  interface Props {
    sessionContents: ISessionContent[];
    hasSessionContents: boolean;
    contentMarginBottom: number;
    isSelectMode?: boolean;
    isMessageSelected?: (messageId: string) => boolean;
  }

  interface Emits {
    (e: 'delete', index: number): void;
    (e: 'regenerate', index: number): void;
    (e: 'resend', index: number, data: { message: string }): void;
    (e: 'message-select', messageId: string): void;
    (e: 'scroll-position-change', isNearBottom: boolean): void;
    (
      e: 'update-session-content',
      data: { messageId: number | undefined; updates: Partial<ISessionContent> }
    ): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const messageWrapper = ref<HTMLElement | null>(null);
  let lastScrollTop = 0;
  const userScrolling = ref(false);

  const getMessageId = (index: number) => {
    return props.sessionContents[index].id;
  };

  const handleUserScroll = () => {
    if (!messageWrapper.value) return;

    userScrolling.value = true;

    const { scrollTop, scrollHeight, clientHeight } = messageWrapper.value;
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50;

    // 发出滚动位置变化事件给父组件
    emit('scroll-position-change', isNearBottom);

    // 只有向下滑动且接近底部时才重置滚动状态
    if (isNearBottom && scrollTop > lastScrollTop) {
      userScrolling.value = false;
    }
    lastScrollTop = scrollTop;
  };

  const scrollToBottom = () => {
    if (messageWrapper.value) {
      messageWrapper.value.scrollTo({
        top: messageWrapper.value.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  const handleMermaidRendered = () => {
    // 在 mermaid 渲染完成后，如果用户没有在滚动，则自动滚动到底部
    setTimeout(() => {
      if (!userScrolling.value) {
        scrollToBottom();
      }
    }, 100);
  };

  const handleDelete = (index: number) => {
    emit('delete', index);
  };

  const handleRegenerate = (index: number) => {
    emit('regenerate', index);
  };

  const handleResend = (index: number, data: { message: string }) => {
    emit('resend', index, data);
  };

  const handleMessageSelect = (messageId: string) => {
    emit('message-select', messageId);
  };

  const handleUpdateSessionContent = (data: {
    messageId: number | undefined;
    updates: Partial<ISessionContent>;
  }) => {
    emit('update-session-content', data);
  };

  const scrollToBottomIfNeeded = () => {
    if (!userScrolling.value) {
      scrollToBottom();
    }
  };

  const resetUserScrolling = () => {
    userScrolling.value = false;
  };

  defineExpose({
    messageWrapper,
    scrollToBottom,
    scrollToBottomIfNeeded,
    userScrolling,
    resetUserScrolling,
  });

  onMounted(() => {
    if (messageWrapper.value) {
      messageWrapper.value.addEventListener('scroll', handleUserScroll);
      messageWrapper.value.addEventListener('mermaid-rendered', handleMermaidRendered);
    }
  });

  onBeforeUnmount(() => {
    if (messageWrapper.value) {
      messageWrapper.value.removeEventListener('scroll', handleUserScroll);
      messageWrapper.value.removeEventListener('mermaid-rendered', handleMermaidRendered);
    }
  });
</script>

<style lang="scss" scoped>
  @use '../styles/mixins.scss';

  .message-wrapper {
    position: relative;
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 32px;
    min-height: 0;
    padding: 0 16px;
    margin-right: -16px;
    margin-bottom: v-bind('props.contentMarginBottom + "px"');
    margin-left: -16px;
    overflow-y: auto;
    transition: opacity 0.5s ease;

    @include mixins.custom-scrollbar;
  }

  .message-line-wrapper {
    width: 100%;
    max-width: var(--ai-blueking-max-width);
    margin: 0 auto;
  }
</style>
