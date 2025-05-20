<template>
  <bk-navigation
    navigation-type="top-bottom"
    :side-title="agentName"
    :need-menu="false"
  >
    <template #side-icon>
      <img src="@/assets/svg/logo.svg">
    </template>
    <template #header>
      <section
        class="home-header"
      >
        <section class="router-links">
          <router-link
            v-for="router in routers"
            :key="router.to"
            :to="{ name: router.to }"
          >
            {{ router.name }}
          </router-link>
        </section>
      </section>
    </template>
    <router-view />
  </bk-navigation>
</template>

<script setup lang="ts">
const agentName = window.BK_AGENT_NAME;

const routers = [
  { to: 'page', name: '聊天窗' },
  { to: 'side-slider', name: '小鲸样例' },
];
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
    color: #96A2B9;
    display: inline-block;
    height: 52px;
    line-height: 52px;
    text-decoration: none;
  }
  .router-link-exact-active, .router-link-active:not(:first-child) {
    color: #FFFFFF;
  }
}

:deep(.bk-navigation-title) {
  max-width: 240px;
}

:deep(.bk-navigation-wrapper .container-content) {
  padding: 0;
}
</style>
