<template>
  <div class="app">
    <nav class="nav">
      <div class="nav-brand">
        <img
          class="nav-logo"
          alt="AI 小鲸"
          src="./blueking-ai.png"
        />
        <span class="nav-title">AI 小鲸</span>
      </div>
      <div class="nav-links">
        <button
          v-for="route in routes"
          :class="{ active: currentRoute === route.key }"
          :key="route.key"
          @click="currentRoute = route.key"
        >
          {{ route.label }}
        </button>
      </div>
      <div class="nav-actions">
        <a
          class="nav-link"
          href="#"
          @click.prevent="showChangelog = true"
          >更新日志</a
        >
        <a
          class="nav-link"
          href="#"
          @click.prevent="showDocs = true"
          >文档</a
        >
      </div>
    </nav>

    <main class="content">
      <DynamicPlayground v-if="currentRoute === 'dynamic'" />
      <Documentation
        v-if="showDocs"
        @close="showDocs = false"
      />
      <Changelog
        v-if="showChangelog"
        @close="showChangelog = false"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import Changelog from './components/changelog-viewer.vue';
  import Documentation from './components/documentation.vue';
  import DynamicPlayground from './dynamic-demo.vue';

  import 'highlight.js/styles/atom-one-dark.css';

  const routes = [{ key: 'dynamic', label: '实时会话样例' }];

  const currentRoute = ref('dynamic');
  // 从 URL 参数中获取初始状态
  const route = new URLSearchParams(window.location.search);
  const showDocs = ref(route.get('docs') === 'true');
  const showChangelog = ref(route.get('changelog') === 'true');
</script>

<style lang="scss">
  body,
  html,
  #app {
    width: 100%;
    height: 100%;
  }

  .app {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    background: #f5f7fa;
  }

  .nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: #fff;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);

    &-brand {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    &-logo {
      width: 32px;
      height: 32px;
    }

    &-title {
      font-size: 20px;
      font-weight: 600;
      color: #1482ff;
    }

    &-links {
      display: flex;
      gap: 12px;

      button {
        padding: 8px 16px;
        font-size: 14px;
        color: #666;
        cursor: pointer;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        transition: all 0.2s;

        &:hover {
          color: #1482ff;
          background: rgba(20, 130, 255, 0.05);
        }

        &.active {
          color: #1482ff;
          background: rgba(20, 130, 255, 0.1);
          border-color: rgba(20, 130, 255, 0.2);
        }
      }
    }

    &-actions {
      display: flex;
      gap: 24px;
    }

    &-link {
      color: #666;
      text-decoration: none;
      transition: color 0.2s;

      &:hover {
        color: #1482ff;
      }
    }
  }

  .content {
    flex: 1;
    padding: 24px;
    overflow: auto;
  }

  // 全局样式重置
  * {
    box-sizing: border-box;
    padding: 0;
    margin: 0;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
</style>
