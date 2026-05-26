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

    <div class="ai-tool-approval-card__processor">
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
        <span class="ai-tool-approval-card__detail-icon" />
      </Button>
      <Button
        v-if="isPendingApproval"
        class="ai-tool-approval-card__cancel"
        outline
        theme="primary"
        @click="handleCancelApproval"
      >
        {{ t('取消审批') }}
      </Button>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import { Button, Loading } from 'bkui-vue';
  import { directive as vTippy } from 'vue-tippy';

  import { APPROVAL_STATUS_MAP } from '../../../ag-ui/types/constants';
  import { APPROVAL_STATUS } from '../../../ag-ui/types/constants';
  import { useClipboard } from '../../../composables';
  import { useCommonTippyInject } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives/overflow-tips';
  import { CheckCircleFillIcon, CloseCircleFillIcon, CopyIcon, RevokedIcon, TimeIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  import type { AIDevToolApprovalInterrupt, OnInterruptResume } from '../../../ag-ui/types/interrupt';

  const props = defineProps<{
    interrupt: AIDevToolApprovalInterrupt;
    onInterruptResume?: OnInterruptResume;
  }>();

  const commonTippyOptions = useCommonTippyInject();
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

  const isPendingApproval = computed(() => pendingStatusSet.has(ticket.value.status));
  const statusClass = computed(() => (isPendingApproval.value ? 'pending' : ticket.value.status));
  const statusText = computed(() =>
    isPendingApproval.value ? t('评审中') : (APPROVAL_STATUS_MAP[ticket.value.status] ?? ticket.value.status),
  );
  const approverText = computed(() => ticket.value.approvers.filter(Boolean).join('、') || t('无'));
  const copyText = computed(() => ticket.value.url || ticket.value.sn);

  const handleOpenDetail = () => {
    if (!ticket.value.url) return;
    window.open(ticket.value.url, '_blank', 'noopener');
  };

  const handleCopy = () => {
    if (!copyText.value) return;
    copy(copyText.value);
  };

  const handleCancelApproval = () => {
    props.onInterruptResume?.(props.interrupt, { action: 'cancel' });
  };
</script>

<style lang="scss">
  .ai-tool-approval-card {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
    padding: 16px;
    font-size: 12px;
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
        width: 50px;
        min-width: 50px;
        color: #979ba5;
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
      flex: 1 1 auto;
      min-width: 0;
      max-width: 296px;
      background: linear-gradient(90deg, #3a84ff 0%, #5a9cff 100%);
      border-color: transparent;
    }

    &__detail-icon {
      position: relative;
      width: 16px;
      height: 16px;
      margin-left: 4px;

      &::before {
        position: absolute;
        top: 4px;
        left: 4px;
        width: 7px;
        height: 7px;
        content: '';
        border-top: 2px solid currentcolor;
        border-right: 2px solid currentcolor;
        transform: rotate(45deg);
      }
    }

    &__cancel {
      flex: 0 0 86px;
    }
  }
</style>
