<template>
  <div class="example-selector">
    <h3>示例选择</h3>
    <div class="example-cards">
      <div
        v-for="example in examples"
        :class="['example-card', { active: modelValue === example.id }]"
        :key="example.id"
        @click="$emit('update:modelValue', example.id)"
      >
        <h4>{{ example.name }}</h4>
        <p>{{ example.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  interface Example {
    id: string;
    name: string;
    description: string;
    config: Record<string, any>;
  }

  defineProps<{
    examples: Example[];
    modelValue: string;
  }>();

  defineEmits<{
    'update:modelValue': [value: string];
  }>();
</script>

<style lang="scss" scoped>
  .example-selector {
    margin-bottom: 32px;

    h3 {
      margin-bottom: 16px;
      font-size: 18px;
      color: #333;
    }
  }

  .example-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 16px;
  }

  .example-card {
    padding: 16px;
    cursor: pointer;
    background: #fff;
    border: 1px solid #eee;
    border-radius: 8px;
    transition: all 0.2s;

    p {
      font-size: 14px;
      color: #666;
    }

    &:hover {
      border-color: #1482ff;
    }

    &.active {
      color: #fff;
      background: #1482ff;
      border-color: #1482ff;

      p {
        color: rgba(255, 255, 255, 0.8);
      }
    }

    h4 {
      margin-bottom: 8px;
      font-size: 16px;
    }
  }
</style>
