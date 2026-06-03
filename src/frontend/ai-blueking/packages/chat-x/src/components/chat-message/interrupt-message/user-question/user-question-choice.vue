<template>
  <div class="ai-user-question-choice">
    <UserQuestionOption
      v-for="(option, oIndex) in displayOptions"
      :key="oIndex"
      :option="option"
      :others-text="othersText"
      :selected="isSelected(oIndex)"
      @confirm="emit('confirm')"
      @select="toggleOption(oIndex)"
      @update:others-text="setOthersText"
    />
  </div>
</template>

<script setup lang="ts">
  import { computed, shallowRef, watch } from 'vue';

  import { type NormalizedUserQuestionOption, OTHERS_OPTION_LABEL, toLetter } from './use-user-question';
  import UserQuestionOption from './user-question-option.vue';

  import type { UserQuestionAnswerItem, UserQuestionItem } from '../../../../ag-ui/types/interrupt';

  const props = defineProps<{
    question: UserQuestionItem;
  }>();

  const emit = defineEmits<{
    // 作答有效时回传已组装答案，无效时回传 undefined（该题视为未作答）
    (e: 'answer', answer: undefined | UserQuestionAnswerItem): void;
    (e: 'confirm'): void;
  }>();

  // 选中项 optionIndex 列表（单选时长度恒为 0/1）
  const selectedIndexes = shallowRef<number[]>([]);
  // Others 自定义输入文本
  const othersText = shallowRef('');

  // 过滤后端可能返回的 others，统一由前端在末尾追加 Others 输入项
  const displayOptions = computed<NormalizedUserQuestionOption[]>(() => {
    const baseOptions = (props.question.options ?? []).filter(option => option.label !== OTHERS_OPTION_LABEL);
    const options: NormalizedUserQuestionOption[] = baseOptions.map((option, index) => ({
      ...option,
      isOthers: false,
      letter: toLetter(index),
    }));
    options.push({ label: OTHERS_OPTION_LABEL, description: '', isOthers: true, letter: toLetter(options.length) });
    return options;
  });

  const othersIndex = computed(() => displayOptions.value.findIndex(option => option.isOthers));

  const isSelected = (optionIndex: number): boolean => selectedIndexes.value.includes(optionIndex);

  // 已作答：至少选中一项；若选中 Others 则要求输入非空
  const answered = computed(() => {
    if (!selectedIndexes.value.length) return false;
    if (othersIndex.value >= 0 && selectedIndexes.value.includes(othersIndex.value)) {
      return othersText.value.trim().length > 0;
    }
    return true;
  });

  const buildAnswer = (): UserQuestionAnswerItem => ({
    question: props.question.question,
    multiSelect: props.question.multiSelect,
    answer: selectedIndexes.value.map(optionIndex => {
      const option = displayOptions.value[optionIndex];
      if (option?.isOthers) {
        return { label: OTHERS_OPTION_LABEL, description: othersText.value.trim() };
      }
      return { label: option?.label ?? '', description: option?.description ?? '' };
    }),
  });

  // 选择/输入变化即同步答案给上层（由 useUserQuestion 聚合计数与 payload）
  const syncAnswer = () => emit('answer', answered.value ? buildAnswer() : undefined);

  // 切换选项：单选直接置为该项，多选则 toggle
  const toggleOption = (optionIndex: number) => {
    const current = selectedIndexes.value;
    selectedIndexes.value = props.question.multiSelect
      ? current.includes(optionIndex)
        ? current.filter(item => item !== optionIndex)
        : [...current, optionIndex]
      : [optionIndex];
    syncAnswer();
  };

  const setOthersText = (text: string) => {
    othersText.value = text;
    syncAnswer();
  };

  // 题目内容变更（如折叠重渲染/切换中断）时重置选择态，避免脏数据
  watch(
    () => props.question,
    () => {
      selectedIndexes.value = [];
      othersText.value = '';
      syncAnswer();
    },
  );
</script>

<style lang="scss">
  .ai-user-question-choice {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
