<template>
  <section class="ai-user-question-answered">
    <header class="ai-user-question-answered__header">
      <div class="ai-user-question-answered__title-wrap">
        <HelpDocIcon class="ai-user-question-answered__help-icon" />
        <span class="ai-user-question-answered__title">{{ t('回答内容') }}</span>
      </div>
      <span class="ai-user-question-answered__status">{{ statusText }}</span>
    </header>

    <div class="ai-user-question-answered__body">
      <div
        v-for="(item, index) in answers"
        :key="index"
        class="ai-user-question-answered__item"
      >
        <div class="ai-user-question-answered__question">
          <span class="ai-user-question-answered__question-text">{{ index + 1 }}. {{ item.question }}</span>
          <span
            v-if="item.multiSelect !== undefined"
            class="ai-user-question-answered__tag"
          >
            {{ item.multiSelect ? t('多选') : t('单选') }}
          </span>
        </div>
        <!-- 默认逐条回显选择题答案；业务方可覆盖此 slot 渲染自定义表单的回显 -->
        <slot
          name="answer"
          v-bind="{ item, index, status }"
        >
          <p
            v-for="(answer, answerIndex) in item.answer"
            :key="answerIndex"
            class="ai-user-question-answered__answer"
          >
            {{ answer.description || answer.label }}
          </p>
        </slot>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { type VNode, computed } from 'vue';

  import { HelpDocIcon } from '../../../../icons';
  import { t } from '../../../../lang/lang';

  import type { UserQuestionAnswerItem } from '../../../../ag-ui/types/interrupt';

  const props = withDefaults(
    defineProps<{
      answers: UserQuestionAnswerItem[];
      // resume 状态：resolved=已回复，cancelled=已取消（跳过）
      status?: 'cancelled' | 'resolved';
    }>(),
    { status: 'resolved' },
  );
  export type UserQuestionAnsweredCardSlots = {
    answer: (props: {
      index: number;
      item: UserQuestionAnswerItem;
      status: 'cancelled' | 'resolved';
    }) => null | undefined | VNode;
  };
  defineSlots<UserQuestionAnsweredCardSlots>();

  const statusText = computed(() => (props.status === 'cancelled' ? t('已取消') : t('已回复')));
</script>

<style lang="scss">
  .ai-user-question-answered {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 326px;
    max-width: 500px;
    font-size: 12px;
    color: #4d4f56;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;

    &__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      background: #f5f7fa;
      border-bottom: 1px solid #dcdee5;
      border-radius: 4px 4px 0 0;
    }

    &__title-wrap {
      display: flex;
      gap: 4px;
      align-items: center;
      min-width: 0;
    }

    &__help-icon {
      flex: 0 0 16px;
      width: 16px;
      height: 16px;
      color: #979ba5;
    }

    &__title {
      font-size: 12px;
      line-height: 20px;
      color: #313238;
    }

    &__status {
      flex: 0 0 auto;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
    }

    &__body {
      display: flex;
      flex-direction: column;
      gap: 16px;
      padding: 8px 0;
    }

    &__item {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 0 16px;
    }

    &__question {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    &__question-text {
      font-size: 12px;
      line-height: 20px;
      color: #313238;
      overflow-wrap: break-word;
    }

    &__tag {
      display: inline-flex;
      flex: 0 0 auto;
      align-items: center;
      height: 16px;
      padding: 0 6px;
      font-size: 12px;
      line-height: 16px;
      color: #1768ef;
      background: #e1ecff;
      border-radius: 2px;
      transform: scale(0.9);
    }

    &__answer {
      margin: 0;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
      overflow-wrap: break-word;
    }
  }
</style>
