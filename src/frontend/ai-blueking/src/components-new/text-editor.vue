<template>
  <div class="bk-text-editor">
    <textarea
      ref="textareaRef"
      class="editor-textarea"
      v-model="inputValue"
      :placeholder="placeholder"
      @compositionend="handleCompositionEnd"
      @compositionstart="handleCompositionStart"
      @input="handleInput"
      @keydown.enter="handleEnter"
    ></textarea>
    <div class="editor-footer">
      <div class="button-group">
        <BkButton
          style="width: 52px; min-width: 52px"
          class="cancel-btn"
          size="small"
          theme="default"
          @click="handleCancel"
        >
          {{ t('取消') }}
        </BkButton>
        <BkButton
          style="width: 52px; min-width: 52px"
          class="submit-btn"
          :disabled="!inputValue.trim()"
          size="small"
          theme="primary"
          @click="handleSubmit"
        >
          {{ t('发送') }}
        </BkButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch, computed, onMounted } from 'vue';

  import { Button as BkButton } from 'bkui-vue';

  import { useInputInteraction } from '../composables/use-input-interaction';
  import { t } from '../lang';

  const props = withDefaults(
    defineProps<{
      modelValue?: string;
      placeholder?: string;
      autoFocus?: boolean;
      loading?: boolean;
    }>(),
    {
      modelValue: '',
      placeholder: t('请输入内容'),
      autoFocus: false,
      loading: false,
    },
  );

  const emit = defineEmits<{
    (e: 'submit' | 'update:modelValue', value: string): void;
    (e: 'cancel' | 'stop'): void;
  }>();

  const textareaRef = ref<HTMLTextAreaElement | null>(null);
  const inputValue = ref(props.modelValue);

  // 使用输入交互组合式函数
  const {
    handleCompositionStart,
    handleCompositionEnd,
    handleEnter: processEnterKey,
    handleSend,
  } = useInputInteraction({
    isLoading: computed(() => props.loading),
    getInputValue: () => inputValue.value,
    clearInput: () => {
      inputValue.value = '';
    },
    onSend: text => emit('submit', text),
    onStop: () => emit('stop'),
  });

  // 监听 modelValue 变化
  watch(
    () => props.modelValue,
    newValue => {
      inputValue.value = newValue;
    },
  );

  // 监听 inputValue 变化
  watch(
    () => inputValue.value,
    newValue => {
      emit('update:modelValue', newValue);
    },
  );

  // 处理输入事件
  const handleInput = () => {
    emit('update:modelValue', inputValue.value);
  };

  // 处理回车事件，自定义增强版本
  const handleEnter = (e: KeyboardEvent) => {
    // 原有的功能：Ctrl/Command + Enter 提交
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      handleSubmit();
      return;
    }

    // 使用组合式函数提供的Enter处理逻辑
    processEnterKey(e);
  };

  // 处理提交事件
  const handleSubmit = () => {
    handleSend(); // 直接使用组合式函数提供的方法
  };

  // 处理取消事件
  const handleCancel = () => {
    inputValue.value = '';
    emit('cancel');
  };

  onMounted(() => {
    if (props.autoFocus) {
      textareaRef.value?.focus();
    }
  });

  // 对外暴露方法
  defineExpose({
    focus: () => {
      textareaRef.value?.focus();
    },
    clear: () => {
      inputValue.value = '';
    },
  });
</script>

<style lang="scss" scoped>
  .bk-text-editor {
    display: flex;
    flex-direction: column;
    width: 100%;
    overflow: hidden;
    font-size: 14px;
    background: #ffffff;
    border: 1px solid #3a84ff;
    border-radius: 4px;

    .editor-textarea {
      width: 100%;
      min-height: 80px;
      padding: 8px 12px;
      font-size: 14px;
      line-height: 20px;
      color: #63656e;
      resize: none;
      background: transparent;
      border: none;
      outline: none;

      &::placeholder {
        color: #c4c6cc;
      }
    }

    .editor-footer {
      display: flex;
      justify-content: flex-end;
      padding: 8px 12px;

      .button-group {
        display: flex;
        gap: 8px;
      }

      .cancel-btn {
        min-width: 68px;
      }

      .submit-btn {
        min-width: 68px;
      }
    }
  }
</style>
