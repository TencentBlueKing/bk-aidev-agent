<template>
  <div class="playground-layout">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">AI</span>
        <span class="logo-text">Blueking Playground</span>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-group">
          <div class="nav-group-title">模式演示</div>
          <RouterLink
            v-for="route in demoRoutes"
            :key="route.path"
            :to="route.path"
            class="nav-item"
            active-class="nav-item--active"
          >
            <span class="nav-dot" />
            {{ route.meta?.title }}
          </RouterLink>
        </div>

        <div class="nav-group">
          <div class="nav-group-title">使用示例</div>
          <RouterLink
            v-for="route in exampleRoutes"
            :key="route.path"
            :to="route.path"
            class="nav-item"
            active-class="nav-item--active"
          >
            <span class="nav-dot" />
            {{ route.meta?.title }}
          </RouterLink>
        </div>
      </nav>
    </aside>

    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

const demoRoutes = computed(() => router.getRoutes().filter(r => r.meta?.group === 'demo'));

const exampleRoutes = computed(() => router.getRoutes().filter(r => r.meta?.group === 'example'));
</script>

<style>
* {
  box-sizing: border-box;
  padding: 0;
  margin: 0;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
}
</style>

<style scoped>
.playground-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  background: #f5f7fa;
}

/* ===== Sidebar ===== */
.sidebar {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  width: 220px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #dcdee5;
}

.sidebar-logo {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 20px 16px;
  border-bottom: 1px solid #f0f1f5;
}

.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: #3a84ff;
  border-radius: 8px;
}

.logo-text {
  font-size: 14px;
  font-weight: 600;
  color: #313238;
}

/* ===== Navigation ===== */
.sidebar-nav {
  flex: 1;
  padding: 12px 0;
  overflow-y: auto;
}

.nav-group {
  margin-bottom: 8px;
}

.nav-group-title {
  padding: 8px 20px 6px;
  font-size: 12px;
  font-weight: 500;
  color: #979ba5;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-item {
  display: flex;
  gap: 8px;
  align-items: center;
  height: 36px;
  padding: 0 20px;
  font-size: 13px;
  color: #63656e;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s;
}

.nav-item:hover {
  color: #3a84ff;
  background: #f0f5ff;
}

.nav-item--active {
  font-weight: 500;
  color: #3a84ff;
  background: #e1ecff;
}

.nav-dot {
  width: 6px;
  height: 6px;
  background: #c4c6cc;
  border-radius: 50%;
  transition: background 0.15s;
}

.nav-item:hover .nav-dot,
.nav-item--active .nav-dot {
  background: #3a84ff;
}

/* ===== Main Content ===== */
.main-content {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}
</style>
