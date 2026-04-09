<template>
  <div
    class="ai-user-feedback"
    @mouseenter.stop.prevent
  >
    <div class="ai-feedback-title">{{ title }}</div>
    <div class="ai-feedback-reason-list">
      <template v-if="loading">
        <div
          v-for="i in 8"
          :key="i"
          class="reason-item ai-skeleton-element"
        />
      </template>
      <template
        v-for="reason in reasonList"
        v-else
        :key="reason"
      >
        <div
          class="reason-item"
          :class="{ 'is-active': selectedReasons.includes(reason) }"
          @click="handleReasonClick(reason)"
        >
          {{ reason }}
        </div>
      </template>
    </div>
    <div class="ai-feedback-other">
      <Input
        v-model="otherReason"
        :placeholder="t('说出您的想法')"
        :rows="3"
        type="textarea"
      />
    </div>
    <div class="ai-feedback-footer">
      <Button
        class="custom-btn"
        :disabled="!otherReason && selectedReasons.length === 0"
        size="small"
        theme="primary"
        @click="handleSubmit"
      >
        {{ t('提交') }}
      </Button>
      <Button
        class="custom-btn"
        size="small"
        width="80px"
        @click="handleCancel"
      >
        {{ t('取消') }}
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { shallowRef } from 'vue';

  import { Button, Input } from 'bkui-vue';

  import { t } from '../../../lang/lang';

  defineProps<{
    loading?: boolean;
    reasonList: string[];
    title: string;
  }>();
  const emit = defineEmits<{
    (e: 'submit', reasonList: string[], otherReason: string): void;
    (e: 'cancel'): void;
  }>();
  const otherReason = shallowRef<string>('');
  const selectedReasons = shallowRef<string[]>([]);
  const handleReasonClick = (reason: string) => {
    if (selectedReasons.value.includes(reason)) {
      selectedReasons.value = selectedReasons.value.filter(r => r !== reason);
    } else {
      selectedReasons.value = [...selectedReasons.value, reason];
    }
  };
  const handleSubmit = () => {
    emit('submit', selectedReasons.value, otherReason.value);
  };
  const handleCancel = () => {
    selectedReasons.value = [];
    otherReason.value = '';
    emit('cancel');
  };
</script>

<style lang="scss">
  .ai-user-feedback {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 400px;
    height: fit-content;
    padding: 16px;
    color: #4d4f56;
    background: #fff;
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 6px 0 #0000001a;

    .ai-feedback-title {
      font-size: 16px;
      line-height: 24px;
      color: #313238;
    }

    .ai-feedback-reason-list {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;

      .ai-skeleton-element {
        width: 70px;
      }

      .reason-item {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 22px;
        padding: 0 8px;
        background: #f0f1f5;
        background-color: #f0f1f5;
        border-radius: 2px;

        &.is-active,
        &:hover {
          color: #1768ef;
          cursor: pointer;
          background-color: #e1ecff;
        }
      }
    }

    .ai-feedback-footer {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;

      .custom-btn {
        width: 64px;
      }
    }
  }
</style>
