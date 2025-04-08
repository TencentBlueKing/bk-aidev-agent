<template>
  <div class="demo-header">
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
  </div>
</template>

<script setup lang="ts">
  withDefaults(
    defineProps<{
      title?: string;
      description?: string;
    }>(),
    {
      title: 'Static Demo',
      description: '开发者测试环境 - 用于前端组件渲染与交互测试',
    },
  );
</script>

<style lang="scss" scoped>
  .demo-header {
    margin-bottom: 40px;
    text-align: center;

    h1 {
      margin-bottom: 16px;
      font-size: 36px;
      background: linear-gradient(45deg, #1482ff, #2dd1f4);
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    p {
      font-size: 16px;
      color: #666;
    }
  }
</style>
