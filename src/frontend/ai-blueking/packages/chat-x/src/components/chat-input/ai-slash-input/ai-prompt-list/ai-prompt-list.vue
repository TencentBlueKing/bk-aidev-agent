<template>
  <div
    ref="promptListRef"
    class="ai-prompt-list"
  >
    <div
      v-for="(prompt, index) in prompts"
      :key="prompt"
      class="ai-prompt-list-item"
      :class="{ 'is-active': activeIndex === index }"
      @click="onSelect(prompt)"
    >
      {{ prompt }}
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, useTemplateRef } from 'vue';

  import { useMenuKeydown } from '../../../../composables/use-menu-keydown';
  const props = defineProps<{
    onSelect: (prompt: string) => void;
    prompts: string[];
  }>();

  const promptListRef = useTemplateRef<HTMLElement>('promptListRef');
  const { activeIndex } = useMenuKeydown<string>({
    items: computed(() => props.prompts),
    onSelect: props.onSelect,
    menuRef: promptListRef,
  });
</script>
<style lang="scss">
  .ai-prompt-list {
    display: flex;
    flex-direction: column;
    width: 330px;
    max-height: 258px;
    padding: 8px;
    overflow-y: auto;
    font-size: 12px;
    color: #4d4f56;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 6px 0 #0000001a;

    .ai-prompt-list-item {
      display: flex;
      align-items: center;
      width: 100%;
      padding: 6px 10px;
      margin-bottom: 4px;
      line-height: 20px;
      background-color: #f5f7fa;

      &:last-child {
        margin-bottom: 0;
      }

      &:hover {
        cursor: pointer;
        background-color: #eaebf0;
      }

      &.is-active {
        background-color: #eaebf0;
      }
    }
  }
</style>
