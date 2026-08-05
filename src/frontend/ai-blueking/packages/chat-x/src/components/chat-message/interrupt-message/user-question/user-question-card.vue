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
      </div>
      <div class="ai-user-question-card__header-actions">
        <div class="ai-user-question-card__pager">
          <button
            class="ai-user-question-card__nav-btn"
            :class="{ 'is-disabled': !canGoPrev }"
            :disabled="!canGoPrev"
            type="button"
            @click.stop="goPrev"
          >
            <ArrowLeftIcon class="ai-user-question-card__nav-icon" />
          </button>
          <span class="ai-user-question-card__pager-text">{{ currentIndex + 1 }} / {{ totalCount }}</span>
          <button
            class="ai-user-question-card__nav-btn"
            :class="{ 'is-disabled': !canGoNext }"
            :disabled="!canGoNext"
            type="button"
            @click.stop="goNext"
          >
            <ArrowRightPreviewIcon class="ai-user-question-card__nav-icon" />
          </button>
        </div>
        <span class="ai-user-question-card__divider" />
        <button
          class="ai-user-question-card__collapse-btn"
          type="button"
          @click.stop="toggleCollapse"
        >
          <ArrowLeftIcon
            class="ai-user-question-card__arrow"
            :style="{ transform: isCollapsed ? 'rotate(180deg)' : 'rotate(-90deg)' }"
          />
        </button>
      </div>
    </header>
    <!-- 折叠用 v-show 而非 v-if：保留 UserQuestionChoice 及自定义 slot 的勾选态，避免卸载丢失选中 -->
    <div
      v-show="!isCollapsed"
      class="ai-user-question-card__body"
    >
      <!-- 一次只展示一题；全部题目仍挂载以保留勾选 / Others 输入态 -->
      <div
        v-for="(question, qIndex) in questions"
        v-show="qIndex === currentIndex"
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

    <footer
      v-show="!isCollapsed"
      class="ai-user-question-card__footer"
    >
      <span class="ai-user-question-card__progress">
        {{ t('已完成') }}
        <span class="ai-user-question-card__progress-num">{{ answeredCount }}</span>
        {{ t('题') }}
      </span>
      <div class="ai-user-question-card__actions">
        <Button
          class="ai-user-question-card__skip"
          :disabled="pendingAction === 'complete'"
          :loading="pendingAction === 'skip'"
          size="small"
          text
          @click="handleSkip"
        >
          <SkipIcon
            v-if="pendingAction !== 'skip'"
            class="ai-user-question-card__skip-icon"
          />
          {{ t('跳过') }}
        </Button>
        <Button
          class="ai-user-question-card__complete"
          :disabled="!completed || pendingAction === 'skip'"
          :loading="pendingAction === 'complete'"
          size="small"
          theme="primary"
          @click="handleComplete"
        >
          <EnterIcon
            v-if="pendingAction !== 'complete'"
            class="ai-user-question-card__enter-icon"
          />
          {{ t('完成') }}
        </Button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
  import { type VNode, computed, shallowRef } from 'vue';

  import { Button } from 'bkui-vue';

  import { useCommonTippyInject } from '../../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { ArrowLeftIcon, ArrowRightPreviewIcon, EnterIcon, HelpDocIcon, SkipIcon } from '../../../../icons';
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
    currentIndex,
    canGoPrev,
    canGoNext,
    goPrev,
    goNext,
    getAnswer,
    setAnswer,
    buildResolvePayload,
    buildSkipPayload,
  } = useUserQuestion(() => props.interrupt);

  const panelTitle = computed(() => props.interrupt.metadata?.questions?.[0]?.header || props.interrupt.message || '');

  const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
  };

  // 折叠态下点击整块可再次展开
  const handleHeaderClick = () => {
    if (isCollapsed.value) {
      isCollapsed.value = false;
    }
  };

  // 完成/跳过为同步 resume，无法拿到请求结果；点击后立即在被点按钮上显示 loading 并禁用两个按钮，
  // 待后台数据刷新使 activeUserQuestionInterrupt 失效（整卡卸载）后该状态随实例销毁自然消失
  const pendingAction = shallowRef<'complete' | 'skip' | null>(null);

  const handleComplete = () => {
    if (!completed.value || pendingAction.value !== null) return;
    pendingAction.value = 'complete';
    props.onResume?.(buildResolvePayload(), props.interrupt);
  };

  const handleSkip = () => {
    if (pendingAction.value !== null) return;
    pendingAction.value = 'skip';
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
    font-size: var(--ai-font-size, 12px);
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
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: #313238;
      white-space: nowrap;
    }

    &__header-actions {
      display: flex;
      flex: 0 0 auto;
      gap: 12px;
      align-items: center;
    }

    &__pager {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    &__pager-text {
      font-family: Arial, sans-serif;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: #979ba5;
      white-space: nowrap;
    }

    &__nav-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      padding: 0;
      color: #979ba5;
      cursor: pointer;
      background: transparent;
      border: none;
      border-radius: 2px;

      &:hover:not(.is-disabled) {
        color: #4d4f56;
        background: #dcdee5;
      }

      &.is-disabled {
        color: #c4c6cc;
        cursor: not-allowed;
        background: #eaebf0;
      }
    }

    &__nav-icon {
      width: 10px;
      height: 10px;

      // stroke 图标的粗细由 stroke-width 控制，覆盖图标默认的 64
      path {
        stroke-width: 120;
      }
    }

    &__divider {
      flex: 0 0 1px;
      width: 1px;
      height: 10px;
      background: #dcdee5;
    }

    &__collapse-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      padding: 0;
      color: #979ba5;
      cursor: pointer;
      background: transparent;
      border: none;
      border-radius: 2px;

      &:hover {
        color: #4d4f56;
      }
    }

    &__arrow {
      width: 12px;
      height: 12px;

      // stroke 图标的粗细由 stroke-width 控制，覆盖图标默认的 64
      path {
        stroke-width: 120;
      }
    }

    &__body {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 320px; // 近似「不超过弹窗 2/3」，可按需调整
      padding: 12px 12px 0;
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
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
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
      justify-content: space-between;
      padding: 12px;
      border-top: 1px solid #dcdee5;
    }

    &__progress {
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: #4d4f56;
      white-space: nowrap;
    }

    &__progress-num {
      font-family: Arial, sans-serif;
    }

    &__actions {
      display: flex;
      gap: 20px;
      align-items: center;
    }

    &__complete,
    &__skip {
      font-size: var(--ai-font-size, 12px) !important;
    }

    &__enter-icon {
      margin-right: 4px;
      font-size: 12px; // 图标尺寸固定，不随 size 主题缩放
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
