<template>
  <div
    class="ai-user-question-option"
    :class="{
      'ai-user-question-option--selected': selected,
      'ai-user-question-option--others': option.isOthers,
    }"
    @click="handleSelect"
  >
    <span class="ai-user-question-option__badge">{{ option.letter }}</span>
    <!-- Others：自定义输入 -->
    <input
      v-if="option.isOthers"
      class="ai-user-question-option__input"
      :placeholder="t('请输入...')"
      :value="othersText"
      @click.stop
      @focus="handleFocus"
      @input="handleInput"
      @keydown.enter.stop="emit('confirm')"
    />
    <span
      v-else
      class="ai-user-question-option__text"
    >
      {{ option.description }}
    </span>
  </div>
</template>

<script setup lang="ts">
  import { t } from '../../../../lang/lang';

  import type { NormalizedUserQuestionOption } from './use-user-question';

  const props = defineProps<{
    option: NormalizedUserQuestionOption;
    othersText?: string;
    selected: boolean;
  }>();

  const emit = defineEmits<{
    (e: 'confirm'): void;
    (e: 'select'): void;
    (e: 'update:othersText', value: string): void;
  }>();

  const handleSelect = () => {
    emit('select');
  };

  const handleFocus = () => {
    if (!props.selected) {
      emit('select');
    }
  };

  const handleInput = (event: Event) => {
    const value = (event.target as HTMLInputElement).value;
    emit('update:othersText', value);
    // 输入即视为选中，保证 Others 与选择态联动
    if (!props.selected) {
      emit('select');
    }
  };
</script>

<style lang="scss">
  .ai-user-question-option {
    display: flex;
    gap: 12px;
    align-items: flex-start; // 内容溢出时徽标顶对齐
    width: 100%;
    padding: 8px 12px;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    transition:
      border-color 0.2s,
      background-color 0.2s;

    &:hover {
      border-color: #699df4;
    }

    &__badge {
      display: inline-flex;
      flex: 0 0 20px;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      font-family: Arial, sans-serif;
      font-size: 12px;
      font-weight: 700;
      line-height: 20px;
      color: #4d4f56;
      background: #dcdee5;
      border-radius: 2px;
    }

    &--selected {
      background: #f0f5ff;
      border-color: #3a84ff;
    }

    &--selected &__badge {
      color: #fff;
      background: #3a84ff;
    }

    &__text {
      flex: 1 1 auto;
      min-width: 0;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      overflow-wrap: break-word;
    }

    &__input {
      flex: 1 1 auto;
      min-width: 0;
      height: 20px;
      padding: 0;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      outline: none;
      background: transparent;
      border: none;

      &::placeholder {
        color: #c4c6cc;
      }
    }
  }
</style>
