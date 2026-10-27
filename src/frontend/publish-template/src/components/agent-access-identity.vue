<template>
  <div class="identity-panel">
    <div class="identity-row">
      <span class="identity-label">当前用户：</span>
      <span class="identity-value">
        <img
          v-if="userAvatar"
          class="identity-avatar"
          :src="userAvatar"
          alt=""
        />
        <img
          v-else
          class="identity-avatar"
          src="@/assets/svg/access-default-avatar.svg"
          alt=""
        />
        <span>{{ userName || "—" }}</span>
      </span>
    </div>
    <div class="identity-row">
      <span class="identity-label">申请智能体：</span>
      <span class="identity-value">
        <img
          class="identity-avatar identity-avatar-agent"
          src="@/assets/svg/logo.svg"
          alt=""
        />
        <span>{{ agentName || "—" }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
  const userName = window.BK_USER_NAME || ""
  const agentName = window.BK_AGENT_NAME || ""
  const userAvatar = window.BK_USER_IMAGE_URL?.trim() || ""
</script>

<style lang="postcss" scoped>
  .identity-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
    align-self: stretch;
    width: 100%;
    box-sizing: border-box;
    padding: 12px 16px;
    background: #f7f9fd;
    border-radius: 2px;
  }

  .identity-row {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  .identity-label {
    flex: 0 0 auto;
    width: 6.5em;
    font-size: 14px;
    line-height: 22px;
    color: #8f9fbd;
    text-align: right;
    white-space: nowrap;
  }

  .identity-value {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    font-size: 14px;
    line-height: 22px;
    color: #4a5973;
  }

  .identity-value span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .identity-avatar {
    display: block;
    width: 16px;
    height: 16px;
    flex: 0 0 16px;
    border-radius: 999px;
    object-fit: cover;
  }
</style>
