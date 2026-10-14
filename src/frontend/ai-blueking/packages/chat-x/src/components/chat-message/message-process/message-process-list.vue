<template>
  <div
    class="ai-message-process"
    :class="{ 'is-enabled': enabled }"
  >
    <MessageProcessHeader
      v-if="enabled"
      :collapsible="collapsible"
      :end-at="bounds.endAt"
      :expanded="collapsible && expanded"
      :label="label"
      :loading="generating"
      :start-at="bounds.startAt"
      @toggle="handleToggle"
    />
    <template
      v-for="message in visibleMessages"
      :key="message.uid || message.id"
    >
      <slot
        :message="message"
        name="message"
      />
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, shallowRef, watch } from 'vue';

  import { t } from '../../../lang/lang';
  import MessageProcessHeader from './message-process-header.vue';
  import { canCollapseProcess, resolveProcessLabelKey } from './message-process-status';
  import { resolveLatestCreatedAt, toTimestamp } from './resolve-process-elapsed';

  import type { Message } from '../../../ag-ui/types';

  const props = withDefaults(
    defineProps<{
      enabled?: boolean;
      /** 本轮是否仍在生成，由容器按「停止生成」按钮的同一判断传入 */
      generating?: boolean;
      messages: Message[];
      /** 本轮对应用户提问的 createdAt，作为耗时起点 */
      requestCreatedAt?: number | string;
    }>(),
    {
      enabled: false,
      generating: false,
    },
  );

  defineSlots<{
    message: (props: { message: Message }) => unknown;
  }>();

  const expanded = shallowRef(false);
  const collapsible = computed(() => canCollapseProcess(props.messages, props.generating));
  const label = computed(() => t(resolveProcessLabelKey(props.messages, props.generating)));
  // 生成中不算耗时；终态从用户提问算到组内最晚的 createdAt，缺任一端则不显示
  const bounds = computed(() => {
    if (props.generating) {
      return { startAt: undefined, endAt: undefined };
    }
    return {
      startAt: toTimestamp(props.requestCreatedAt),
      endAt: resolveLatestCreatedAt(props.messages),
    };
  });

  // 可折叠时默认只留最后一条；生成中、单条或用户展开后展示全部
  const visibleMessages = computed(() => {
    if (!props.enabled || !collapsible.value || expanded.value) {
      return props.messages;
    }
    const lastMessage = props.messages.at(-1);
    return lastMessage ? [lastMessage] : [];
  });

  // 再次进入可折叠状态时收回过程，例如本轮中途展开后又继续生成
  watch(collapsible, value => {
    if (value) {
      expanded.value = false;
    }
  });

  const handleToggle = () => {
    if (!collapsible.value) {
      return;
    }
    expanded.value = !expanded.value;
  };
</script>
<style lang="scss">
  .ai-message-process {
    display: contents;

    &.is-enabled {
      display: flex;
      flex-direction: column;
      gap: 8px;
      width: 100%;
      min-width: 0;
    }
  }
</style>
