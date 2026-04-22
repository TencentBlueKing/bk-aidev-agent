<template>
  <div class="ai-interrupt-choice-list">
    <div class="ai-interrupt-choice-list-divider" />
    <p class="ai-interrupt-choice-list-title">{{ titleText }}</p>
    <div class="ai-interrupt-choice-list-options">
      <InterruptOptionBtn
        v-for="choice in payload.choices"
        :key="choice.value"
        :description="choice.description"
        :disabled="disabled || submitting || choice.disabled"
        :label="choice.label ?? choice.value"
        :selected="selectingValues.includes(choice.value)"
        @click="handleToggle(choice)"
      />
    </div>
    <Button
      class="ai-interrupt-choice-list-submit"
      :disabled="submitDisabled"
      :loading="submitting"
      theme="primary"
      @click="handleSubmit"
    >
      {{ t('继续') }}
    </Button>
  </div>
</template>

<script setup lang="ts">
  import { computed, shallowRef } from 'vue';

  import { Button } from 'bkui-vue';

  import { InterruptReason } from '../../../ag-ui/types/constants';
  import { t } from '../../../lang/lang';
  import InterruptOptionBtn from './interrupt-option-btn.vue';

  import type { UserChoice } from '../../../ag-ui/types/interrupt';
  import type { InterruptChoiceListProps } from './types';

  const props = defineProps<InterruptChoiceListProps>();

  const selectingValues = shallowRef<string[]>(toInitialSelected(props));
  const submitting = shallowRef(false);

  const isMulti = computed(() => props.payload.type === InterruptReason.UserMultiChoice);

  const titleText = computed(() => props.payload.title || t('请选择以继续'));

  const submitDisabled = computed(() => props.disabled || submitting.value || selectingValues.value.length === 0);

  const handleToggle = (choice: UserChoice) => {
    if (props.disabled || submitting.value || choice.disabled) {
      return;
    }
    if (isMulti.value) {
      const next = selectingValues.value.includes(choice.value)
        ? selectingValues.value.filter(v => v !== choice.value)
        : [...selectingValues.value, choice.value];
      selectingValues.value = next;
      return;
    }
    selectingValues.value = [choice.value];
  };

  const handleSubmit = async () => {
    if (submitDisabled.value) {
      return;
    }
    const values = selectingValues.value;
    const choices = props.payload.choices.filter(c => values.includes(c.value));
    submitting.value = true;
    try {
      await props.onSubmit(values, choices);
    } finally {
      submitting.value = false;
    }
  };

  function toInitialSelected(p: InterruptChoiceListProps): string[] {
    const raw = p.payload.selected;
    if (Array.isArray(raw)) {
      return [...raw];
    }
    if (typeof raw === 'string' && raw) {
      return [raw];
    }
    return [];
  }
</script>

<style lang="scss">
  .ai-interrupt-choice-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;

    &-divider {
      width: 100%;
      height: 1px;
      background-color: #dcdee5;
    }

    &-title {
      margin: 0;
      font-size: 12px;
      font-weight: 700;
      line-height: 20px;
      color: #4d4f56;
    }

    &-options {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
    }

    &-submit {
      align-self: flex-start;
    }
  }
</style>
