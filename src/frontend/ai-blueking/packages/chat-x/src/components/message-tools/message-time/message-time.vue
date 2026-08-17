<template>
  <span
    v-if="displayTime"
    class="ai-message-time"
  >
    {{ displayTime }}
  </span>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { injectGlobalConfig } from '../../../composables/use-global-config';
  import { formatMessageTime } from './format-message-time';

  export type MessageTimeProps = {
    createdAt?: number | string;
    /** IANA 时区名；优先于全局配置，两者都未配置时按浏览器时区展示 */
    timezone?: string;
  };
  const props = defineProps<MessageTimeProps>();
  const globalConfig = injectGlobalConfig();

  const timezone = computed(() => props.timezone ?? globalConfig?.timezone?.value);
  const displayTime = computed(() => formatMessageTime(props.createdAt, timezone.value));
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-message-time {
    flex: none;
    font-size: var(--ai-font-size, 12px);
    line-height: 16px;
    color: variables.$color-text-secondary;
    white-space: nowrap;
  }
</style>
