<template>
  <div
    v-if="visible"
    class="auth-success-mask"
    role="dialog"
    aria-modal="true"
    aria-labelledby="auth-success-title"
  >
    <AgentAccessCard>
      <AgentAccessStatusIcon type="success" />
      <h1
        id="auth-success-title"
        class="access-title"
      >
        授权成功
      </h1>
      <p class="access-desc">已授权成功，您现在可关闭此窗口或返回应用</p>
      <div class="auth-identity-wrap">
        <AgentAccessIdentity />
      </div>
      <template #actions>
        <AgentAccessButton
          auto-width
          @click="emit('return')"
        >
          返回企业微信
        </AgentAccessButton>
      </template>
    </AgentAccessCard>
  </div>
</template>

<script setup lang="ts">
  import AgentAccessButton from "./agent-access-button.vue"
  import AgentAccessCard from "./agent-access-card.vue"
  import AgentAccessIdentity from "./agent-access-identity.vue"
  import AgentAccessStatusIcon from "./agent-access-status-icon.vue"

  interface AuthorizationSuccessDialogProps {
    visible: boolean
  }

  interface AuthorizationSuccessDialogEmits {
    (event: "return"): void
  }

  defineProps<AuthorizationSuccessDialogProps>()
  const emit = defineEmits<AuthorizationSuccessDialogEmits>()
</script>

<style lang="postcss" scoped>
  .auth-success-mask {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.4);
  }

  .access-title {
    width: 100%;
    margin: 0;
    font-size: 20px;
    font-weight: 400;
    line-height: 28px;
    color: #111214;
    text-align: center;
  }

  .access-desc {
    width: 100%;
    margin: 0;
    font-size: 14px;
    line-height: 22px;
    color: #4a5973;
    text-align: center;
  }

  .auth-identity-wrap {
    align-self: stretch;
    box-sizing: border-box;
    width: 100%;
    padding: 16px;
    background: #f7f9fd;
  }
</style>
