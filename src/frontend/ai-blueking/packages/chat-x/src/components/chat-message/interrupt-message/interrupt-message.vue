<template>
  <InterruptResult
    v-if="showResult"
    :selected-labels="resultLabels"
    :title="resultTitle"
  />
  <InterruptChoiceList
    v-else-if="showChoiceList && choicePayload"
    :on-submit="handleSubmit"
    :payload="choicePayload"
  />
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import { InterruptReason, RunFinishedOutcome } from '../../../ag-ui/types/constants';
  import { t } from '../../../lang/lang';
  import InterruptChoiceList from './interrupt-choice-list.vue';
  import InterruptResult from './interrupt-result.vue';
  import { SUPPORTED_INTERRUPT_REASONS } from './types';

  import type {
    InterruptMessage,
    InterruptResumePayload,
    OnInterruptResume,
    UserChoice,
    UserChoicePayload,
  } from '../../../ag-ui/types/interrupt';

  const props = defineProps<
    Partial<InterruptMessage> & {
      onInterruptResume?: OnInterruptResume;
    }
  >();

  const interruptData = computed(() => props.interrupt);

  const choicePayload = computed<undefined | UserChoicePayload<'multi' | 'single'>>(() => {
    const data = interruptData.value;
    if (!data?.payload?.choices?.length) {
      return undefined;
    }
    if (!SUPPORTED_INTERRUPT_REASONS.includes(data.reason)) {
      return undefined;
    }
    return data.payload;
  });

  const isMulti = computed(() => choicePayload.value?.type === InterruptReason.UserMultiChoice);

  const showResult = computed(() => props.outcome === RunFinishedOutcome.Success);

  const showChoiceList = computed(() => !showResult.value && Boolean(choicePayload.value));

  const resultTitle = computed(() => t('收到信息：'));

  const resultLabels = computed<string[]>(() => {
    const fromSelected = readSelectedFromPayload();
    if (fromSelected.length > 0) {
      return fromSelected;
    }
    if (typeof props.result === 'string' && props.result) {
      return [props.result];
    }
    if (Array.isArray(props.result)) {
      return props.result.map(item => String(item));
    }
    return [];
  });

  const handleSubmit = async (selectedValues: string[], selectedChoices: UserChoice[]) => {
    const data = interruptData.value;
    if (!data) {
      return;
    }
    const selected: string | string[] = isMulti.value ? [...selectedValues] : (selectedValues[0] ?? '');
    // 回写到原 message，便于刷新/会话恢复时初始化展示，与上报回调保持单一数据源
    data.payload.selected = selected as never;

    const payload: InterruptResumePayload = {
      interruptId: data.id,
      selected,
      selectedChoices,
    };
    await props.onInterruptResume?.(props as InterruptMessage, payload);
  };

  function readSelectedFromPayload(): string[] {
    const data = interruptData.value;
    if (!data?.payload?.choices) {
      return [];
    }
    const selected = data.payload.selected;
    const values = Array.isArray(selected) ? selected : selected ? [selected] : [];
    return values
      .map(v => data.payload.choices.find(c => c.value === v))
      .filter((c): c is UserChoice => Boolean(c))
      .map(c => c.label ?? c.value);
  }
</script>
