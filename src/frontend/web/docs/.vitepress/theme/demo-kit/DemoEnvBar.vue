<template>
  <div class="demo-env-bar">
    <span class="demo-env-bar__label">演示环境</span>
    <div
      class="demo-seg"
      role="radiogroup"
      aria-label="演示后端"
    >
      <button
        type="button"
        role="radio"
        :aria-checked="state.backendMode === 'mock'"
        :class="{ 'is-on': state.backendMode === 'mock' }"
        @click="runtime.setBackendMode('mock')"
      >
        <span class="demo-seg__dot" />Mock
      </button>
      <button
        type="button"
        role="radio"
        :aria-checked="state.backendMode === 'real'"
        :class="{ 'is-on': state.backendMode === 'real' }"
        :disabled="!runtime.canUseReal"
        :title="runtime.canUseReal ? '连接站点配置的 AIDev 智能体' : '站点未配置 BK_AIDEV_API_URL'"
        @click="runtime.setBackendMode('real')"
      >
        <span class="demo-seg__dot is-real" />真实智能体
      </button>
    </div>
    <span class="demo-env-bar__desc">
      本页所有配方共用右侧同一个小鲸实例{{ state.backendMode === 'real' ? '，当前回答来自真实智能体' : '' }}
    </span>
    <button
      type="button"
      class="demo-link"
      @click="runtime.reset()"
    >
      重置演示
    </button>
  </div>
</template>

<script setup lang="ts">
  import { useDemoRuntime } from './use-demo-runtime';

  const runtime = useDemoRuntime();
  const { state } = runtime;
</script>
