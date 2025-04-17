<template>
  <div class="chat-input-box">
    <AiSelectedBox
      v-if="selectedText.length > 0"
      style="margin-bottom: 10px"
      :actions="props.shortcuts"
      :selected-text="selectedText"
      @mousedown.prevent
      @shortcut-click="handleShortcutClick"
    />
    <ShortcutsBar
      v-else
      style="margin-bottom: 8px"
      :shortcuts="shortcuts"
      @shortcut-click="handleShortcutClickWithClear"
    />
    <div class="input-wrapper">
      <PromptList
        ref="promptListRef"
        class="prompt-list-wrapper"
        v-model:show="showPromptList"
        :prompts="props.prompts"
        @height-change="handlePromptHeightChange"
        @select="handlePromptSelect"
      />
      <div
        v-if="citeText.length > 0"
        class="cite"
      >
        <AiCite
          :show-close-icon="true"
          :text="citeText"
          @close="setCiteText('')"
        />
      </div>
      <textarea
        ref="textareaRef"
        :style="{ height: textareaHeight + 'px' }"
        class="input-area"
        v-model="inputValue"
        :placeholder="placeholder"
        @compositionend="handleCompositionEnd"
        @compositionstart="handleCompositionStart"
        @focus="handleFocus"
        @input="handleInput"
        @keydown="handleKeyDown"
      />
      <div class="input-tools">
        <i
          ref="actionIconRef"
          :class="['bkai-icon', actionIconClass, { disabled: !loading && !inputValue.trim() }, 'clickable']"
          @click="handleActionClick"
        ></i>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref, onMounted, watch, computed, onBeforeUnmount } from 'vue';
  import { ComponentPublicInstance } from 'vue';

  import { type ShortCut } from '@blueking/ai-ui-sdk';
  import { Instance } from 'tippy.js';

  import AiCite from '../components/ai-cite.vue';
  import { useInputInteraction } from '../composables/use-input-interaction';
  import { usePopup } from '../composables/use-popup-props';
  import { useSelect } from '../composables/use-select-pop';
  import { useTextareaHeight } from '../composables/use-textarea-height';
  import { useTooltip } from '../composables/use-tippy';
  import { t } from '../lang';
  import AiSelectedBox from './ai-selected-box.vue';
  import PromptList from './prompt-list.vue';
  import ShortcutsBar from './shortcuts-bar.vue';

  const emit = defineEmits<{
    (e: 'send' | 'update:modelValue', value: string): void;
    (e: 'stop'): void;
    (e: 'height-change', height: number): void;
    (e: 'shortcut-click', shortcut: ShortCut): void;
  }>();
  const placeholder = t('输入 "/" 唤出 Prompt\n通过 Shift + Enter 进行换行输入');

  const { enablePopup } = usePopup();
  const { selectedText, citeText, setCiteText, clearSelection, lockSelectedText } = useSelect(enablePopup);

  const props = defineProps<{
    shortcuts: ShortCut[];
    loading: boolean;
    prompts: string[];
  }>();

  const textareaRef = ref<HTMLTextAreaElement>();
  const inputValue = ref('');

  const promptListRef = ref<ComponentPublicInstance | null>(null);
  const promptHeight = ref(0);

  const promptListTop = computed(() => {
    const offset = 8;
    return -(promptHeight.value + offset) + 'px';
  });

  const showPromptList = ref(false);

  const handlePromptSelect = (prompt: string) => {
    inputValue.value = prompt;
    showPromptList.value = false;
  };

  // 动态计算按钮图标类和tooltip文本
  const actionIconRef = ref<HTMLElement>();
  const actionTooltip = ref<Instance>();
  const actionIconClass = computed(() => {
    return props.loading ? 'icon-published-zhongzhi' : 'icon-fasong';
  });
  const actionTooltipText = computed(() => {
    return props.loading ? t('停止') : t('发送');
  });
  const isActionDisabled = computed(() => {
    return !props.loading && !inputValue.value.trim();
  });

  const { createTooltip } = useTooltip({
    arrow: true,
    delay: [0, 0],
  });

  // 处理合并后的操作按钮点击事件
  const handleActionClick = () => {
    if (props.loading) {
      handleStop();
    } else {
      handleSend();
    }
  };

  // 初始化 tooltip
  const initTooltip = () => {
    if (actionIconRef.value) {
      actionTooltip.value = createTooltip(actionIconRef.value, actionTooltipText.value, {
        appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
      }) as Instance;
    }

    updateTooltip();
  };

  // 更新 tooltip 内容
  const updateTooltip = () => {
    if (actionTooltip.value) {
      actionTooltip.value.setContent(actionTooltipText.value);

      // 根据按钮状态启用或禁用tooltip
      if (isActionDisabled.value) {
        actionTooltip.value.disable();
      } else {
        actionTooltip.value.enable();
      }
    }
  };

  // textarea 高度
  const { textareaHeight, updateHeight, resetHeight, bindTextarea } = useTextareaHeight({
    minHeight: 68,
    maxHeight: 248,
    defaultHeight: 68,
  });

  const handleShortcutClickWithClear = (shortcut: ShortCut) => {
    handleShortcutClick(shortcut);
    inputValue.value = '';
  };

  const handleShortcutClick = (shortcut: ShortCut) => {
    emit('shortcut-click', shortcut);
    clearSelection();
  };

  // 使用输入交互组合式函数
  const {
    isComposing,
    handleCompositionStart,
    handleCompositionEnd,
    handleSend: onSend,
    handleStop,
  } = useInputInteraction({
    isLoading: computed(() => props.loading),
    getInputValue: () => inputValue.value,
    clearInput: () => {
      inputValue.value = '';
      resetHeight(); // 重置高度
    },
    onSend: text => emit('send', text),
    onStop: () => emit('stop'),
  });

  // 监听citeText变化，如果citeText有值，则将焦点设置到textarea
  watch(citeText, () => {
    if (citeText.value.length > 0) {
      textareaRef.value?.focus();
    }
  });

  // 监听文本高度变化
  watch(
    () => textareaHeight.value,
    newHeight => {
      emit('height-change', newHeight);
    },
  );

  // 监听加载状态和输入内容变化，更新tooltip
  watch([() => props.loading, () => inputValue.value], () => {
    updateTooltip();
  });

  const handleInput = () => {
    // 如果是组合输入阶段，不更新高度
    if (!isComposing.value) {
      // 更新文本区域高度
      updateHeight();
    }

    // 如果有内容且有 selectedText， 则需要把 selectedText 框选内容清空
    if ((inputValue.value.trim() || isComposing.value) && selectedText.value) {
      selectedText.value = '';
    }

    if (inputValue.value.includes('/')) {
      showPromptList.value = true;
    } else {
      showPromptList.value = false;
    }

    // 触发 v-model 更新
    emit('update:modelValue', inputValue.value);
  };

  const handleFocus = () => {
    if (selectedText.value) {
      lockSelectedText.value = true;
    }
  };

  // 封装自定义的handleSend方法，在发送前进行最后的检查
  const handleSend = () => {
    if (!inputValue.value.trim()) return;
    onSend();
  };

  // 添加点击外部关闭提示列表的功能
  const handleDocumentClick = (event: MouseEvent) => {
    if (showPromptList.value) {
      const promptListEl = promptListRef.value?.$el as HTMLElement;
      const textareaEl = textareaRef.value;

      // 如果点击的不是提示列表和输入框，则关闭提示列表
      if (
        promptListEl &&
        !promptListEl.contains(event.target as Node) &&
        textareaEl !== event.target &&
        !textareaEl?.contains(event.target as Node)
      ) {
        showPromptList.value = false;
      }
    }
  };

  onMounted(() => {
    if (textareaRef.value) {
      // 绑定文本区域元素
      bindTextarea(textareaRef.value);
      emit('height-change', textareaHeight.value); // 初始化时发送高度
    }

    initTooltip();

    // 添加点击事件监听
    document.addEventListener('click', handleDocumentClick);
  });

  onBeforeUnmount(() => {
    // 移除事件监听
    document.removeEventListener('click', handleDocumentClick);
  });

  // 直接处理高度变化事件
  const handlePromptHeightChange = (height: number) => {
    promptHeight.value = height;
  };

  // 修改键盘事件处理
  const handleKeyDown = (event: KeyboardEvent) => {
    // 如果提示列表显示中，让提示列表组件处理方向键和Enter键
    if (showPromptList.value && ['ArrowDown', 'ArrowUp', 'Enter'].includes(event.key)) {
      const promptList = promptListRef.value as ComponentPublicInstance & {
        handleArrowDown: () => void;
        handleArrowUp: () => void;
        handleEnter: () => boolean;
      };
      if (!promptList) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault(); // 阻止默认行为（滚动页面）
        promptList.handleArrowDown();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault(); // 阻止默认行为（滚动页面）
        promptList.handleArrowUp();
      } else if (event.key === 'Enter') {
        const handled = promptList.handleEnter();
        if (handled) {
          event.preventDefault(); // 如果提示列表处理了Enter键，阻止默认行为
        }
      }
      return;
    }

    // 现有的键盘事件处理逻辑
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  // 封装自定义的sendMessage方法
  const sendMessage = () => {
    if (!inputValue.value.trim()) return;
    handleSend();
  };
</script>

<style lang="scss" scoped>
  .chat-input-box {
    width: 100%;
    background: #ffffff;
    border-radius: 8px;

    .prompt-list-wrapper {
      position: absolute;
      top: v-bind(promptListTop);
    }

    .input-wrapper {
      position: relative;
      width: 100%;
      background:
        linear-gradient(#fff, #fff) padding-box,
        linear-gradient(180deg, #6cbaff 0%, #3a84ff 100%) border-box;
      border: 1px solid transparent;
      border-radius: 8px;

      .cite {
        margin: 8px 8px 0 8px;

        :deep(.content) {
          justify-content: space-between;
          width: 100%;
        }
      }
    }

    .input-area {
      width: 100%;
      min-height: 68px;
      max-height: 248px;
      padding: 8px 8px 0 8px;
      overflow-y: auto;
      font-size: 14px;
      line-height: 20px;
      color: #63656e;
      resize: none;
      background: transparent;
      border: none;
      outline: none;

      &::placeholder {
        line-height: 20px;
        color: #c4c6cc;
        white-space: pre-line;
      }

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #e5e5e5;
        border-radius: 2px;
      }
    }

    .input-tools {
      display: flex;
      align-items: flex-start;
      justify-content: flex-end;
      height: 32px;
      padding: 0 12px;

      .bkai-icon {
        font-size: 16px;
        color: #63656e;
        cursor: pointer;

        &.icon-fasong {
          margin-right: 0;
        }

        &.clickable {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          font-size: 14px;
          color: #fff;
          background: #3a84ff;
          border-radius: 4px;

          &:hover {
            color: #fff;
            background: #1768ef;
          }

          &.disabled {
            color: #c4c6cc;
            cursor: not-allowed;
            background: #f0f1f5;
          }
        }

        &:hover {
          color: #3a84ff;
        }
      }

      .send-tip {
        font-size: 12px;
        color: #979ba5;
      }
    }
  }
</style>
