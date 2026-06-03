<template>
  <section
    class="ai-user-question-card"
    :class="{ 'ai-user-question-card--collapsed': isCollapsed }"
  >
    <header
      class="ai-user-question-card__header"
      @click="handleHeaderClick"
    >
      <div class="ai-user-question-card__title-wrap">
        <HelpDocIcon class="ai-user-question-card__help-icon" />
        <span
          v-overflow-tips="{ ...commonTippyOptions }"
          class="ai-user-question-card__title"
        >
          {{ panelTitle }}
        </span>
        <!-- <span
          v-if="isCollapsed"
          class="ai-user-question-card__tag"
        >
          {{ headerSelectText }}
        </span> -->
      </div>
      <div class="ai-user-question-card__counter-wrap">
        <span class="ai-user-question-card__counter">{{ answeredCount }} / {{ totalCount }}</span>
        <ArrowLeftIcon
          class="ai-user-question-card__arrow"
          :style="{ transform: isCollapsed ? 'rotate(180deg)' : 'rotate(-90deg)' }"
          @click.stop="toggleCollapse"
        />
      </div>
    </header>

    <template v-if="!isCollapsed">
      <div class="ai-user-question-card__body">
        <div
          v-for="(question, qIndex) in questions"
          :key="qIndex"
          class="ai-user-question-card__question"
        >
          <div class="ai-user-question-card__question-title">
            <span class="ai-user-question-card__question-text">{{ qIndex + 1 }}. {{ question.question }}</span>
            <span
              v-if="question.multiSelect !== undefined"
              class="ai-user-question-card__tag"
            >
              {{ question.multiSelect ? t('多选') : t('单选') }}
            </span>
          </div>
          <div class="ai-user-question-card__options">
            <!-- 默认渲染选择题；业务方可覆盖此 slot 渲染任意表单，作答有效时通过 setAnswer 回传 -->
            <slot
              name="question"
              v-bind="{
                question,
                qIndex,
                answer: getAnswer(qIndex),
                setAnswer: (answer: undefined | UserQuestionAnswerItem) => setAnswer(qIndex, answer),
                confirm: handleComplete,
              }"
            >
              <UserQuestionChoice
                :question="question"
                @answer="setAnswer(qIndex, $event)"
                @confirm="handleComplete"
              />
            </slot>
          </div>
        </div>
      </div>

      <footer class="ai-user-question-card__footer">
        <Button
          class="ai-user-question-card__complete"
          :disabled="!completed"
          size="small"
          theme="primary"
          @click="handleComplete"
        >
          <EnterIcon class="ai-user-question-card__enter-icon" />
          {{ t('完成') }}
        </Button>
        <Button
          class="ai-user-question-card__skip"
          size="small"
          text
          @click="handleSkip"
        >
          <SkipIcon class="ai-user-question-card__skip-icon" />
          {{ t('跳过') }}
        </Button>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
  import { type VNode, computed, shallowRef } from 'vue';

  import { Button } from 'bkui-vue';

  import { useCommonTippyInject } from '../../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { ArrowLeftIcon, EnterIcon, HelpDocIcon, SkipIcon } from '../../../../icons';
  import { t } from '../../../../lang/lang';
  import { useUserQuestion } from './use-user-question';
  import UserQuestionChoice from './user-question-choice.vue';

  import type {
    OnInterruptResume,
    UserQuestionAnswerItem,
    UserQuestionInterrupt,
    UserQuestionItem,
  } from '../../../../ag-ui/types/interrupt';

  const props = defineProps<{
    interrupt: UserQuestionInterrupt;
    onResume?: OnInterruptResume;
  }>();
  export type UserQuestionCardSlots = {
    question: (props: {
      // 当前题已组装答案（undefined 表示未作答）
      answer: undefined | UserQuestionAnswerItem;
      // 触发「完成」（等价点击完成按钮）
      confirm: () => void;
      qIndex: number;
      // 原始题目数据
      question: UserQuestionItem;
      // 写入/清空当前题答案；作答有效传已组装答案，无效传 undefined
      setAnswer: (answer: undefined | UserQuestionAnswerItem) => void;
    }) => null | undefined | VNode;
  };
  defineSlots<UserQuestionCardSlots>();

  // 注入通用 tippy 配置（供标题溢出提示使用）
  const commonTippyOptions = useCommonTippyInject();

  const isCollapsed = shallowRef(false);

  const {
    questions,
    answeredCount,
    totalCount,
    completed,
    getAnswer,
    setAnswer,
    buildResolvePayload,
    buildSkipPayload,
  } = useUserQuestion(() => props.interrupt);

  const panelTitle = computed(() => props.interrupt.metadata?.questions?.[0]?.header || props.interrupt.message || '');
  // 折叠态标题旁的 单选/多选 标签，取首题类型作近似展示
  // const headerSelectText = computed(() =>
  //   props.interrupt.metadata?.questions?.[0]?.multiSelect ? t('多选') : t('单选'),
  // );

  const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
  };

  // 折叠态下点击整块可再次展开
  const handleHeaderClick = () => {
    if (isCollapsed.value) {
      isCollapsed.value = false;
    }
  };

  const handleComplete = () => {
    if (!completed.value) return;
    props.onResume?.(buildResolvePayload(), props.interrupt);
  };

  const handleSkip = () => {
    props.onResume?.(buildSkipPayload(), props.interrupt);
  };
</script>

<style lang="scss">
  @use '../../../../styles/variables.scss' as variables;

  .ai-user-question-card {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: variables.$chat-input-min-width;
    max-width: variables.$chat-input-max-width;
    margin-bottom: 8px;
    font-size: 12px;
    color: #4d4f56;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 12px;
    box-shadow: 0 0 5px 0 rgb(0 0 0 / 10%);

    &--collapsed {
      cursor: pointer;
      background: #f0f1f5;
    }

    &__header {
      display: flex;
      flex: 0 0 40px;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      height: 40px;
      padding: 0 16px;
      background: #f0f1f5;
      border-bottom: 1px solid #dcdee5;
      border-radius: 12px 12px 0 0;
    }

    &--collapsed &__header {
      border-bottom: none;
      border-radius: 12px;
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
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 12px;
      line-height: 20px;
      color: #313238;
      white-space: nowrap;
    }

    &__counter-wrap {
      display: flex;
      flex: 0 0 auto;
      gap: 4px;
      align-items: center;
    }

    &__counter {
      font-family: Arial, sans-serif;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
    }

    &__arrow {
      width: 12px;
      height: 12px;
      color: #979ba5;
      cursor: pointer;

      // stroke 图标的粗细由 stroke-width 控制，覆盖图标默认的 64
      path {
        stroke-width: 120;
      }

      &:hover {
        color: #4d4f56;
      }
    }

    &__body {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 320px; // 近似「不超过弹窗 2/3」，可按需调整
      padding: 12px;
      overflow-y: auto;
      scrollbar-color: #dcdee5 transparent;
      scrollbar-width: thin;

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #dcdee5;
        border-radius: 2px;
      }
    }

    &__question {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    &__question-title {
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

    &__options {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    &__footer {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 12px;
      border-top: 1px solid #dcdee5;
    }

    &__enter-icon {
      margin-right: 4px;
      font-size: 12px;
      line-height: 1;
    }

    &__skip-icon {
      width: 14px;
      height: 14px;
      margin-right: 4px;
      color: rgb(151 155 165 / 100%);
    }

    &__skip {
      color: #4d4f56;
    }
  }
</style>
