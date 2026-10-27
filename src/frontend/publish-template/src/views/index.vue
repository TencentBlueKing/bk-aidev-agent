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

<style lang="postcss" scoped>
  .home-header {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 20px;
  }

  .router-links {
    a {
      font-size: 14px;
      margin-right: 35px;
      color: #96a2b9;
      display: inline-block;
      height: 52px;
      line-height: 52px;
      text-decoration: none;
    }
    .router-link-exact-active,
    .router-link-active:not(:first-child) {
      color: #ffffff;
    }
  }

  :deep(.bk-navigation-title) {
    max-width: 240px;
  }

  :deep(.bk-navigation-wrapper .container-content) {
    padding: 0;
  }

  .access-gate {
    width: 100%;
    height: 100vh;
  }
</style>
