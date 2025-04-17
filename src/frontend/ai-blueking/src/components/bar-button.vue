<template>
  <div
    class="bar-button"
    @click="emit('click')"
  >
    <i
      class="bkai-icon"
      :class="props.icon"
    ></i>
    <span class="bar-button-text">{{ props.text }}</span>
  </div>
</template>

<script setup lang="ts">
  const emit = defineEmits<{
    click: [];
  }>();

  const props = defineProps<{
    icon: string;
    color?: string;
    text: string;
  }>();
</script>

<style lang="scss" scoped>
  .bar-button {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 24px;
    padding: 0 10px;
    cursor: pointer;
    background: #ffffff;
    border: 1px solid #dcdee5;
    border-radius: 26px;
    box-shadow: 0 -2px 6px 0 #0000001a;

    &:hover {
      border: 1px solid #c4c6cc;
      box-shadow: 0 -2px 6px 0 #00000026;
    }

    .bkai-icon {
      font-size: 14px;
      color: v-bind(color);
    }

    .bar-button-text {
      font-size: 12px;
      color: #4d4f56;
    }
  }
</style>
