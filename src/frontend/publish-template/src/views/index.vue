<template>
  <div
    v-if="!gateReady"
    class="access-gate"
    v-bkloading="{
      loading: true,
      theme: 'primary',
      mode: 'spin',
    }"
  />
  <bk-navigation
    v-else
    navigation-type="top-bottom"
    :side-title="agentName"
    :need-menu="false"
  >
    <template #side-icon>
      <img src="@/assets/svg/logo.svg" />
    </template>
    <template #header>
      <section class="home-header">
        <section class="router-links">
          <router-link
            v-for="router in routers"
            :key="router.to"
            :to="{ name: router.to }"
          >
            {{ router.name }}
          </router-link>
        </section>
        <section class="user-name" style="font-size: 14px; color: #7b7d8a">
          {{ userName }}
        </section>
      </section>
    </template>
    <router-view />
  </bk-navigation>
</template>

<script setup lang="ts">
  import { onBeforeMount, ref } from "vue"
  import { useRouter } from "vue-router"

  import { loadAgentAccess, useAgentAccess } from "../composables/use-agent-access"

  const agentName = window.BK_AGENT_NAME

  const userName = window.BK_USER_NAME
  const routers = [
    { to: "chat-window", name: "聊天窗" },
    { to: "side-slider", name: "小鲸样例" },
  ]
  const router = useRouter()
  const gateReady = ref(false)
  const { accessState } = useAgentAccess()

  onBeforeMount(async () => {
    await loadAgentAccess(true)
    if (accessState.status !== "authorized") {
      await router.replace({
        name: "agent-access",
        query: router.currentRoute.value.query,
      })
      return
    }
    gateReady.value = true
  })
</script>

<style lang="postcss">
  :root {
    --aidev-horiz-nav-background: #0c1323;
    --aidev-horiz-nav-item-color: #96a2b9;
    --aidev-horiz-nav-item-active-color: #ffffff;
    --aidev-horiz-nav-item-hover-color: #ffffff;
    --aidev-horiz-nav-item-hover-background: #31394f;
    --aidev-horiz-nav-item-active-after-background: linear-gradient(155deg, #4abdfb 0%, #425bfb 51%, #4551fb 100%);
    --aidev-radius: 6px;
    --aidev-radius-s: 2px;
    --aidev-logo-background: #ffffff;
    --aidev-workbench-aside-background: #f0f4fa;
    --aidev-workbench-session-list-color: #4a5973;
    --aidev-workbench-session-list-active-color: #3b6ef5;
    --aidev-workbench-session-list-active-background: #e5edff;
    --aidev-workbench-session-list-active-border-color: #c7d8ff;
    --aidev-workbench-session-list-hover-background: #ffffff;
    --aidev-form-border-color: #c1cde5;
    --aidev-form-hover-border-color: #8f9fbd;
    --aidev-form-active-border-color: #3b6ef5;
    --aidev-form-background: #ffffff;
    --aidev-form-color: #4a5973;
    --aidev-form-placeholder-color: #c1cde5;
    --aidev-basic-button-hover-color: #111214;
    --aidev-line-strong-color: #e4e9f2;
    --aidev-line-weak-color: #f0f4fa;
    --aidev-main-color: #4a5973;
    --aidev-main-background: #ffffff;
    --aidev-title-color: #111214;
    --aidev-assist-color: #8f9fbd;
    --aidev-workbench-session-list-time-color: #8f9fbd;
    --aidev-clickable-color: #3b6ef5;
    --aidev-checkbox-background: #ffffff;
    --aidev-checkbox-border-color: #8f9fbd;
    --aidev-checkbox-hover-border-color: #3b6ef5;
    --aidev-checkbox-checked-color: #3b6ef5;
    --aidev-checkbox-checked-mark-color: #ffffff;
    --aidev-main-button-color: #ffffff;
    --aidev-main-button-background: #3b6ef5;
    --aidev-main-button-border-color: #3b6ef5;
    --aidev-main-button-hover-background: #6691ff;
    --aidev-main-button-hover-border-color: #6691ff;
    --aidev-main-button-active-background: #274ecf;
    --aidev-main-button-active-border-color: #274ecf;
    --aidev-main-button-box-shadow: 0 4px 10px #3b6ef540;
    --aidev-background: #f7f9fd;
    --aidev-assist-content-background: #f0f4fa;
    --aidev-danger-button-color: #ea3636;
    --aidev-danger-button-border-color: #ea3636;
    --aidev-dialog-box-shadow: 0 4px 12px #00000033;
    --aidev-icon-hover-background: #c7d8ff;
    --aidev-icon-light-hover-background: #f0f4ff;
    --aidev-item-hover-background: #e5edff;
    --aidev-resize-collapse-background: #e4e9f2;
    --aidev-resize-collapse-color: #ffffff;
  }
</style>

<style lang="postcss" scoped>
  .home-header {
    width: 100%;
    min-width: 0;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 14px;
  }

  .router-links {
    display: flex;
    align-items: center;
    height: 100%;
    min-width: 0;

    a {
      position: relative;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      height: 30px;
      padding: 0 8px;
      margin-right: 16px;
      font-size: 14px;
      line-height: 1;
      color: var(--aidev-horiz-nav-item-color);
      border-radius: var(--aidev-radius);
      text-decoration: none;

      &:hover {
        color: var(--aidev-horiz-nav-item-hover-color);
        background: var(--aidev-horiz-nav-item-hover-background);
      }
    }

    .router-link-exact-active,
    .router-link-active:not(:first-child) {
      color: var(--aidev-horiz-nav-item-active-color);

      &::after {
        content: "";
        position: absolute;
        left: 50%;
        bottom: 0;
        width: 24px;
        height: 4px;
        border-radius: var(--aidev-radius);
        background: var(--aidev-horiz-nav-item-active-after-background);
        transform: translateX(-50%);
      }
    }
  }

  :deep(.bk-navigation-header) {
    background: var(--aidev-horiz-nav-background);
  }

  :deep(.bk-navigation-title) {
    max-width: 240px;
  }

  :deep(.bk-navigation-title .title-icon) {
    flex: 0 0 28px;
    width: 28px;
    height: 32px;
  }

  :deep(.bk-navigation-title .title-icon img) {
    width: 28px;
    height: 32px;
  }

  :deep(.bk-navigation-title .title-desc) {
    margin-left: 16px;
    font-size: 16px;
    font-weight: 700;
    line-height: 24px;
    color: var(--aidev-logo-background);
  }

  :deep(.bk-navigation-wrapper .container-content) {
    padding: 0;
  }

  .access-gate {
    width: 100%;
    height: 100vh;
  }
</style>
