<template>
  <section class="ai-tool-approval-card">
    <header class="ai-tool-approval-card__header">
      <div class="ai-tool-approval-card__title-wrap">
        <span class="ai-tool-approval-card__title-bar" />
        <span class="ai-tool-approval-card__title">{{ ticket.title || t('算法方案评审单') }}</span>
        <CopyIcon
          v-tippy="{ ...commonTippyOptions, content: t('复制单据链接'), theme: 'ai-chat-box', offset: [0, 8] }"
          class="ai-tool-approval-card__copy-icon"
          :class="{ 'is-disabled': !copyText }"
          @click="handleCopy"
        />
        <!-- 审批中态提供刷新图标：取消为后端轮询、无法实时返回，用户可手动拉取单据最新状态；每次刷新 2s 冷却 -->
        <RebuildIcon
          v-if="isPendingApproval && !readonly"
          v-tippy="{ ...commonTippyOptions, content: t('刷新单据状态'), theme: 'ai-chat-box', offset: [0, 8] }"
          class="ai-tool-approval-card__refresh-icon"
          :class="{ 'is-disabled': refreshCooldown || isShareContext }"
          @click="handleRefresh"
        />
      </div>
      <span
        class="ai-tool-approval-card__status"
        :class="`ai-tool-approval-card__status--${statusClass}`"
      >
        <CheckCircleFillIcon
          v-if="ticket.status === APPROVAL_STATUS.APPROVED"
          class="ai-tool-approval-card__status-icon"
        />
        <CloseCircleFillIcon
          v-else-if="dangerStatusSet.has(ticket.status)"
          class="ai-tool-approval-card__status-icon"
        />
        <RevokedIcon
          v-else-if="ticket.status === APPROVAL_STATUS.REVOKED"
          class="ai-tool-approval-card__status-icon"
          :class="{ 'ai-tool-approval-card__status-icon--revoked': ticket.status === APPROVAL_STATUS.REVOKED }"
        />
        <Loading
          v-else
          class="ai-tool-approval-card__status-icon"
          mode="spin"
          size="mini"
          theme="primary"
        />
        {{ statusText }}
      </span>
    </header>

    <dl class="ai-tool-approval-card__fields">
      <div class="ai-tool-approval-card__field">
        <dt>{{ t('单据编号') }}</dt>
        <dd>{{ ticket.sn || '--' }}</dd>
      </div>
      <div class="ai-tool-approval-card__field">
        <dt>{{ t('提交时间') }}</dt>
        <dd>{{ ticket.submit_time || '--' }}</dd>
      </div>
    </dl>
    <!-- 工具参数展示：内容超过 3 行时支持展开/收起，无参数时不渲染 -->
    <ToolApprovalArgs :tool-args="interrupt.metadata?.toolArgs" />
    <div
      v-if="isPendingApproval"
      class="ai-tool-approval-card__processor"
    >
      <TimeIcon class="ai-tool-approval-card__processor-icon" />
      <span
        v-overflow-tips="{ ...commonTippyOptions }"
        class="ai-tool-approval-card__processor-text"
      >
        {{ t('当前处理人') }}：{{ approverText }}
      </span>
    </div>

    <div class="ai-tool-approval-card__actions">
      <Button
        class="ai-tool-approval-card__detail"
        :disabled="!ticket.url"
        theme="primary"
        @click="handleOpenDetail"
      >
        {{ t('查看单据详情') }}
        <ArrowLeftIcon class="ai-tool-approval-card__detail-icon" />
      </Button>
      <!-- 待审批态：可点「取消审批」；点击后按钮进入 loading（同步 resume 无结果，防重复提交） -->
      <Button
        v-if="isPendingApproval && !readonly"
        class="ai-tool-approval-card__cancel"
        :disabled="cancelling || isShareContext"
        :loading="cancelling"
        outline
        theme="primary"
        @click="handleCancelApproval"
      >
        {{ t('取消审批') }}
      </Button>
      <!-- 终态：保留「取消审批」按钮但置灰，hover 显示当前状态无法取消的原因（tooltip 挂在外层 span，规避 disabled 按钮不触发 hover） -->
      <span
        v-else-if="!readonly"
        v-tippy="{ ...commonTippyOptions, content: cancelDisabledTip, theme: 'ai-chat-box', offset: [0, 8] }"
        class="ai-tool-approval-card__cancel-wrap"
      >
        <Button
          class="ai-tool-approval-card__cancel"
          disabled
          outline
        >
          {{ cancelButtonText }}
        </Button>
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { computed, onUnmounted, shallowRef } from 'vue';

  import { Button, Loading } from 'bkui-vue';
  import { directive as vTippy } from 'vue-tippy';

  import { APPROVAL_STATUS_MAP } from '../../../ag-ui/types/constants';
  import { APPROVAL_STATUS } from '../../../ag-ui/types/constants';
  import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
  import { RenderMode } from '../../../common/constants';
  import { useClipboard } from '../../../composables';
  import { useCommonTippyInject, useRenderModeInject } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives/overflow-tips';
  import {
    ArrowLeftIcon,
    CheckCircleFillIcon,
    CloseCircleFillIcon,
    CopyIcon,
    RebuildIcon,
    RevokedIcon,
    TimeIcon,
  } from '../../../icons';
  import { t } from '../../../lang/lang';
  import ToolApprovalArgs from './tool-approval-args.vue';

  import type { AIDevToolApprovalInterrupt, OnInterruptResume } from '../../../ag-ui/types/interrupt';

  // 刷新单据状态的冷却时长（ms）：取消为后端轮询，短时间内重复刷新无意义
  const REFRESH_COOLDOWN_MS = 2000;

  const props = defineProps<{
    interrupt: AIDevToolApprovalInterrupt;
    onInterruptResume?: OnInterruptResume;
    // 只读回显态（outcome.success 结果回显）：隐藏取消审批按钮，不接受交互
    readonly?: boolean;
  }>();

  const commonTippyOptions = useCommonTippyInject();
  const renderMode = useRenderModeInject();
  // 只读分享渲染（RenderMode.Share）下禁用审批单的交互按钮
  const isShareContext = computed(() => renderMode.value === RenderMode.Share);
  const { copy } = useClipboard();
  const pendingStatusSet = new Set([APPROVAL_STATUS.PENDING, APPROVAL_STATUS.DRAFT]);
  const dangerStatusSet = new Set([
    APPROVAL_STATUS.ABANDONED,
    APPROVAL_STATUS.CANCELLED,
    APPROVAL_STATUS.EXPIRED,
    APPROVAL_STATUS.REJECTED,
  ]);

  const ticket = computed(
    () =>
      props.interrupt.metadata?.ticket ?? {
        approvers: [],
        sn: '',
        status: APPROVAL_STATUS.PENDING,
        submit_time: '',
        title: '',
        url: '',
      },
  );

  // 用户自行取消 / 撤销后的终态：按钮文案改为「已取消审批」
  const cancelledStatusSet = new Set([APPROVAL_STATUS.CANCELLED, APPROVAL_STATUS.REVOKED]);
  // 各终态下「取消审批」置灰按钮的 hover 提示；未覆盖的终态（已废弃 / 已过期等）走通用兜底文案
  const cancelDisabledTipMap: Partial<Record<APPROVAL_STATUS, string>> = {
    [APPROVAL_STATUS.APPROVED]: t('该单据已通过，无法取消'),
    [APPROVAL_STATUS.CANCELLED]: t('单据已取消审批'),
    [APPROVAL_STATUS.REJECTED]: t('该单据已被拒绝，无法取消'),
    [APPROVAL_STATUS.REVOKED]: t('单据已取消审批'),
  };

  const isPendingApproval = computed(() => pendingStatusSet.has(ticket.value.status));
  const statusClass = computed(() => (isPendingApproval.value ? 'pending' : ticket.value.status));
  const statusText = computed(() =>
    isPendingApproval.value ? t('审批中') : (APPROVAL_STATUS_MAP[ticket.value.status] ?? ticket.value.status),
  );
  const approverText = computed(() => ticket.value.approvers.filter(Boolean).join('、') || t('无'));
  const copyText = computed(() => ticket.value.url || ticket.value.sn);
  const cancelButtonText = computed(() =>
    cancelledStatusSet.has(ticket.value.status) ? t('已取消审批') : t('取消审批'),
  );
  const cancelDisabledTip = computed(() => cancelDisabledTipMap[ticket.value.status] ?? t('当前状态无法取消审批'));

  const handleOpenDetail = () => {
    if (!ticket.value.url) return;
    window.open(ticket.value.url, '_blank', 'noopener');
  };

  const handleCopy = () => {
    if (!copyText.value) return;
    copy(copyText.value);
  };

  // 取消审批为同步 resume，无法拿到请求结果；点击后按钮立即进入 loading 并禁用防重复提交，
  // 待后台数据刷新使按钮 v-if 失效（卡片卸载/重建）后该状态随实例销毁自然消失
  const cancelling = shallowRef(false);
  // 刷新为后端轮询、无法实时返回，故做 2s 冷却节流：冷却中刷新图标置灰不可点
  const refreshCooldown = shallowRef(false);
  let cooldownTimer: ReturnType<typeof setTimeout> | undefined;

  const startRefreshCooldown = () => {
    refreshCooldown.value = true;
    clearTimeout(cooldownTimer);
    cooldownTimer = setTimeout(() => {
      refreshCooldown.value = false;
    }, REFRESH_COOLDOWN_MS);
  };

  const handleCancelApproval = () => {
    if (cancelling.value) return;
    cancelling.value = true;
    // 取消后进入后台轮询，2s 内不允许刷新，之后可继续手动刷新拉取最新状态
    startRefreshCooldown();
    props.onInterruptResume?.(
      { operation: InterruptResumeOperation.ApprovalCancel, payload: { interrupt_id: props.interrupt.id } },
      props.interrupt,
    );
  };

  const handleRefresh = () => {
    if (refreshCooldown.value || isShareContext.value) return;
    startRefreshCooldown();
    props.onInterruptResume?.(
      { operation: InterruptResumeOperation.ApprovalRefresh, payload: { interrupt_id: props.interrupt.id } },
      props.interrupt,
    );
  };

  onUnmounted(() => clearTimeout(cooldownTimer));
</script>

<style lang="scss">
  .ai-tool-approval-card {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
    padding: 16px;
    font-size: var(--ai-font-size, 12px);
    line-height: 18px;
    color: #4d4f56;
    background: linear-gradient(145deg, #f7f9ff 0%, #f9faff 25%, #fafcff 50%, #fcfdff 75%, #fff 100%);
    border: 1px solid #e3ebff;
    border-radius: 4px;
    box-shadow: 0 1px 1.5px 0 rgb(0 0 0 / 10%);

    &__header {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      min-width: 0;
    }

    &__title-wrap {
      display: flex;
      gap: 8px;
      align-items: center;
      min-width: 0;
    }

    &__title-bar {
      flex: 0 0 4px;
      width: 4px;
      height: 16px;
      background: linear-gradient(180deg, #3a84ff 0%, #6ca6ff 100%);
      border-radius: 8px;
    }

    &__title {
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 13px;
      line-height: 20px;
      color: #313238;
      white-space: nowrap;
    }

    &__copy-icon {
      flex: 0 0 16px;
      width: 16px;
      height: 16px;
      color: #699df4;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }

      &.is-disabled {
        color: #c4c6cc;
        cursor: not-allowed;
      }
    }

    &__refresh-icon {
      flex: 0 0 16px;
      width: 16px;
      height: 16px;
      color: #699df4;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }

      &.is-disabled {
        color: #c4c6cc;
        cursor: not-allowed;
      }
    }

    &__status {
      display: inline-flex;
      flex: 0 0 auto;
      gap: 4px;
      align-items: center;
      height: 26px;
      padding: 0 12px;
      color: #ff9c00;
      background: #fff4e6;
      border-radius: 13px;

      &--pending {
        color: #3a84ff;
        background: #e1ecff;
      }

      &--approved {
        color: #14a568;
        background: #e4faf0;
      }

      &--rejected,
      &--cancelled,
      &--expired,
      &--abandoned {
        color: #ea3636;
        background: #ffe6e6;
      }

      &--revoked {
        color: #f59500;
        background: #fdeed8;
      }
    }

    &__status-icon {
      flex: 0 0 16px;
      width: 16px;
      height: 16px;

      &--revoked {
        flex-basis: 18px;
        width: 18px;
        height: 18px;
      }
    }

    &__fields {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
    }

    &__field {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-width: 0;

      dt {
        flex-shrink: 0;
        color: #979ba5;
        white-space: nowrap;
      }

      dd {
        max-width: 70%;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        color: #4d4f56;
        text-align: right;
        white-space: nowrap;
      }
    }

    &__processor {
      display: flex;
      gap: 4px;
      align-items: center;
      height: 44px;
      padding: 0 12px;
      background: #fff;
      border: 1px solid #f0f1f5;
      border-radius: 4px;
    }

    &__processor-icon {
      flex: 0 0 16px;
      width: 16px;
      height: 16px;
      color: #3a84ff;
    }

    &__processor-text {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      color: #4d4f56;
      white-space: nowrap;
    }

    &__actions {
      display: flex;
      gap: 8px;
      height: 32px;

      .bk-button {
        height: 32px;
        font-size: 13px;
        border-radius: 2px;
      }
    }

    &__detail {
      flex: 0 1 auto;
      width: 296px;
      max-width: 296px;
      background: linear-gradient(90deg, #3a84ff 0%, #5a9cff 100%);
      border-color: transparent;
    }

    &__detail-icon {
      width: 12px;
      height: 12px;
      margin-left: 4px;
      font-size: 12px;
      transform: rotate(180deg);

      path {
        stroke-width: 120;
      }
    }

    &__cancel {
      flex: 1 0 auto;
      min-width: 86px;
    }

    &__cancel-wrap {
      display: inline-flex;
      flex: 1 0 auto;
    }
  }
</style>
