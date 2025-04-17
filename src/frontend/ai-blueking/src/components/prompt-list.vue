<template>
  <div
    ref="promptListEl"
    class="bkai-prompt-list"
    v-show="show"
  >
    <div class="bkai-prompt-list-search">
      <Input
        v-model="searchValue"
        behavior="simplicity"
        placeholder="请输入关键词"
      />
    </div>
    <div class="bkai-prompt-list-content">
      <div
        v-if="filteredPrompts.length === 0"
        class="bkai-prompt-list-empty"
      >
        {{ t('无匹配结果') }}
      </div>
      <div
        v-for="(prompt, index) in filteredPrompts"
        v-else
        style="overflow: hidden"
        class="bkai-prompt-list-item"
        :class="{ active: activeIndex === index }"
        :key="prompt"
        @click="handleSelect(prompt)"
        @mouseleave="activeIndex = null"
        @mouseover="activeIndex = index"
      >
        {{ prompt }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { nextTick, ref, computed, onMounted, onBeforeUnmount, defineExpose, watch } from 'vue';

  import { Input } from 'bkui-vue';

  import { t } from '../lang';

  const props = defineProps<{
    prompts: string[];
    show: boolean;
  }>();

  const emit = defineEmits<{
    (e: 'select', prompt: string): void;
    (e: 'height-change', height: number): void;
    (e: 'update:show', value: boolean): void;
  }>();

  const searchValue = ref('');
  const promptListEl = ref<HTMLElement | null>(null);
  const activeIndex = ref<null | number>(null);

  const filteredPrompts = computed(() => {
    if (!searchValue.value.trim()) return props.prompts;
    return props.prompts.filter(prompt => prompt.toLowerCase().includes(searchValue.value.toLowerCase()));
  });

  watch(
    () => props.show,
    newVal => {
      if (newVal) {
        nextTick(() => {
          activeIndex.value = null;
        });
      }
    },
  );

  // 处理选择项
  const handleSelect = (prompt: string) => {
    emit('select', prompt);
    emit('update:show', false);
    searchValue.value = '';
  };

  // 处理键盘导航
  const handleArrowDown = () => {
    if (!filteredPrompts.value.length) return;

    if (activeIndex.value === null || activeIndex.value === filteredPrompts.value.length - 1) {
      activeIndex.value = 0;
    } else {
      activeIndex.value++;
    }
    scrollToActiveItem();
  };

  const handleArrowUp = () => {
    if (!filteredPrompts.value.length) return;

    if (activeIndex.value === null || activeIndex.value === 0) {
      activeIndex.value = filteredPrompts.value.length - 1;
    } else {
      activeIndex.value--;
    }
    scrollToActiveItem();
  };

  const handleEnter = (): boolean => {
    if (!filteredPrompts.value.length || activeIndex.value === null) return false;

    handleSelect(filteredPrompts.value[activeIndex.value]);
    return true;
  };

  // 滚动到选中项
  const scrollToActiveItem = () => {
    if (activeIndex.value === null || !promptListEl.value) return;

    const contentEl = promptListEl.value.querySelector('.bkai-prompt-list-content') as HTMLElement;
    if (!contentEl) return;

    const activeItem = contentEl.children[activeIndex.value] as HTMLElement;
    if (!activeItem) return;

    const contentRect = contentEl.getBoundingClientRect();
    const activeItemRect = activeItem.getBoundingClientRect();

    // 如果选中项在可视区域之上，滚动到选中项顶部
    if (activeItemRect.top < contentRect.top) {
      contentEl.scrollTop = activeItem.offsetTop;
    }
    // 如果选中项在可视区域之下，滚动到选中项底部
    else if (activeItemRect.bottom > contentRect.bottom) {
      contentEl.scrollTop = activeItem.offsetTop + activeItem.offsetHeight - contentEl.clientHeight;
    }
  };

  // 使用 ResizeObserver 监听元素大小变化
  let resizeObserver: ResizeObserver | null = null;

  onMounted(() => {
    if (promptListEl.value) {
      resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          // 通知父组件高度变化
          emit('height-change', entry.contentRect.height);
        }
      });

      resizeObserver.observe(promptListEl.value);
    }
  });

  onBeforeUnmount(() => {
    if (resizeObserver && promptListEl.value) {
      resizeObserver.unobserve(promptListEl.value);
      resizeObserver.disconnect();
    }
  });

  // 对外暴露方法
  defineExpose({
    handleArrowDown,
    handleArrowUp,
    handleEnter,
  });
</script>

<style lang="scss" scoped>
  @import '../styles/mixins.scss';

  .bkai-prompt-list {
    z-index: 1000;
    display: flex;
    flex-direction: column;
    width: 100%;
    max-height: 258px;
    background: #ffffff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 0 8px 0 #0000001a;

    .bkai-prompt-list-search {
      padding: 0 8px;
    }

    .bkai-prompt-list-content {
      flex: 1;
      padding: 8px;
      overflow-y: auto;

      @include custom-scrollbar;

      .bkai-prompt-list-item {
        display: -webkit-box;
        max-height: 52px; /* 2行文字的大约高度 */
        padding: 4px 12px;
        overflow: hidden;
        font-size: 12px;
        line-height: 20px;
        color: #4d4f56;
        text-overflow: ellipsis;
        cursor: pointer;
        background: #f5f7fa;
        border-radius: 4px;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;

        &:not(:last-child) {
          margin-bottom: 4px;
        }

        &:hover,
        &.active {
          background: #eaebf0;
        }
      }
    }
  }

  .bkai-prompt-list-empty {
    padding: 12px;
    font-size: 12px;
    color: #979ba5;
    text-align: center;
  }
</style>
