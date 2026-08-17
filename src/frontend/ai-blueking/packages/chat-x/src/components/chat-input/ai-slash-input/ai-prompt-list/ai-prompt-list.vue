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
    box-sizing: border-box;
    width: 100%;
    max-height: 320px; // 与 @ 菜单一致：10 * 32px
    padding: 8px;
    overflow: hidden auto;
    font-size: var(--ai-font-size, 12px);
    color: #4d4f56;
    background: #fff;
    border: 0;
    border-radius: 8px;
    outline: none;
    box-shadow: none; // 外阴影由 tippy-box 承担，避免被裁切
    scrollbar-color: #dcdee5 transparent;
    scrollbar-width: thin;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;

      &:hover {
        background: #c4c6cc;
      }
    }

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
