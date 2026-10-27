<template>
  <span class="status-icon">
    <img
      v-if="type === 'success'"
      src="@/assets/svg/access-status-success.svg"
      alt=""
    />
    <img
      v-else
      src="@/assets/svg/access-status-error.svg"
      alt=""
    />
  </span>
</template>

<script setup lang="ts">
  interface AgentAccessStatusIconProps {
    type: "success" | "error"
  }

  defineProps<AgentAccessStatusIconProps>()
</script>

<style lang="postcss" scoped>
  .status-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
  }

  .status-icon img {
    display: block;
    width: 42px;
    height: 42px;
  }
</style>
