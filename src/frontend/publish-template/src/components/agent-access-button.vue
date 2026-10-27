<template>
  <bk-button
    class="access-action"
    :class="actionClass"
    v-bind="buttonAttrs"
    @click="emit('click')"
  >
    <slot />
  </bk-button>
</template>

<script setup lang="ts">
  import { computed } from "vue"

  interface AgentAccessButtonProps {
    theme?: "primary" | "plain"
    loading?: boolean
    disabled?: boolean
    /** 按文案宽度展示，用于「返回企业微信」 */
    autoWidth?: boolean
  }

  interface AgentAccessButtonEmits {
    (event: "click"): void
  }

  const props = withDefaults(defineProps<AgentAccessButtonProps>(), {
    theme: "plain",
    loading: false,
    disabled: false,
    autoWidth: false,
  })

  const emit = defineEmits<AgentAccessButtonEmits>()

  const actionClass = computed(() => {
    if (props.theme === "primary") {
      return "access-action-primary"
    }
    return props.autoWidth ? "access-action-auto" : "access-action-plain"
  })

  const buttonAttrs = computed(() => {
    const attrs: { theme?: "primary"; loading: boolean; disabled: boolean } = {
      loading: props.loading,
      disabled: props.disabled || props.loading,
    }
    if (props.theme === "primary") {
      attrs.theme = "primary"
    }
    return attrs
  })
</script>

<style lang="postcss" scoped>
  .access-action {
    box-sizing: border-box;
    width: 88px;
    height: 32px;
    min-width: 88px;
    padding: 0 16px;
    border-radius: 6px;
    font-size: 14px;
    line-height: 22px;
  }

  .access-action.access-action-primary {
    color: #fff;
    background-color: #3b6ef5;
    border-color: #3b6ef5;
    box-shadow: 0 4px 10px rgba(59, 110, 245, 0.25);
  }

  .access-action.access-action-primary:hover,
  .access-action.access-action-primary:active {
    color: #fff;
    background-color: #3b6ef5;
    border-color: #3b6ef5;
  }

  .access-action.access-action-plain,
  .access-action.access-action-auto {
    color: #4a5973;
    background: #fff;
    border-color: #c1cde5;
  }

  .access-action.access-action-auto {
    width: auto;
  }

  .access-action.access-action-plain:hover,
  .access-action.access-action-plain:active,
  .access-action.access-action-auto:hover,
  .access-action.access-action-auto:active {
    color: #4a5973;
    background: #fff;
    border-color: #c1cde5;
  }
</style>
