<template>
  <div class="demo-stage">
    <div class="demo-stage__chrome">
      <span
        class="demo-stage__dots"
        aria-hidden="true"
      ><i /><i /><i /></span>
      <span class="demo-stage__app">{{ app }}</span>
      <span
        v-if="crumbs"
        class="demo-stage__crumbs"
      >/ {{ crumbs }}</span>
      <span class="demo-stage__tag">模拟宿主页面</span>
    </div>
    <div class="demo-stage__body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
  interface DemoStageProps {
    /** 模拟应用名，如「蓝鲸监控」 */
    app: string;
    /** 面包屑，如「告警中心 / 告警详情」 */
    crumbs?: string;
  }

  withDefaults(defineProps<DemoStageProps>(), { crumbs: '' });
</script>
