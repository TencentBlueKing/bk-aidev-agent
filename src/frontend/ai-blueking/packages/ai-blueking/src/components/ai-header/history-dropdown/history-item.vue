<template>
  <div
    class="history-item"
    :class="{ active: props.isActive }"
    @click="handleClick"
  >
    <template v-if="!props.isEditing">
      <bk-overflow-title style="width: calc(100% - 42px)">
        {{ props.session.sessionName }}
      </bk-overflow-title>
      <span class="history-item-actions">
        <i
          v-bk-tooltips="{
            content: t('编辑'),
            boundary: 'parent',
          }"
          class="bkai-icon bkai-bianji"
          @click.stop="handleEdit"
        ></i>
        <bk-pop-confirm
          :title="t('确认删除会话 ?')"
          content="删除操作无法撤回，请谨慎操作!"
          :confirm-config="{
            theme: 'danger',
          }"
          trigger="click"
          boundary="parent"
          @confirm="handleDelete"
        >
          <i
            v-bk-tooltips="{
              content: t('删除'),
              boundary: 'parent',
            }"
            class="bkai-icon bkai-shanchu"
            @click.stop
          ></i>
        </bk-pop-confirm>
      </span>
    </template>
    <bk-input
      v-else
      ref="editInputRef"
      v-model="editingName"
      style="width: 100%; height: 28px"
      @blur="handleRenameConfirm"
      @keyup="handleKeyup"
      @click.stop
    />
  </div>
</template>

<script setup lang="ts">
  import {
    Input as BkInput,
    PopConfirm as BkPopConfirm,
    OverflowTitle as BkOverflowTitle,
    bkTooltips,
  } from 'bkui-vue';
  import { ref, watch, nextTick } from 'vue';

  import { t } from '../../../lang';
  import type { HistoryItemProps, HistoryItemEmits } from './types';

  const props = defineProps<HistoryItemProps>();
  const emit = defineEmits<HistoryItemEmits>();

  const vBkTooltips = bkTooltips;
  const editInputRef = ref<InstanceType<typeof BkInput> | null>(null);
  const editingName = ref('');

  // 监听编辑状态，自动聚焦输入框
  watch(
    () => props.isEditing,
    newVal => {
      if (newVal) {
        editingName.value = props.session.sessionName;
        nextTick(() => {
          if (editInputRef.value) {
            try {
              const bkInputInstance = editInputRef.value;
              if (bkInputInstance && typeof bkInputInstance.focus === 'function') {
                bkInputInstance.focus();
              }
              const inputElement = (bkInputInstance.$el as HTMLElement)?.querySelector('input');
              if (inputElement && typeof inputElement.select === 'function') {
                inputElement.select();
              }
            } catch (error) {
              console.warn('Failed to focus edit input:', error);
            }
          }
        });
      }
    }
  );

  const handleClick = () => {
    if (!props.isEditing) {
      emit('click', props.session);
    }
  };

  const handleEdit = () => {
    emit('edit', props.session);
  };

  const handleDelete = () => {
    emit('delete', props.session.sessionCode);
  };

  const handleRenameConfirm = () => {
    const newName = editingName.value.trim();
    if (newName && newName !== props.session.sessionName) {
      emit('rename-confirm', props.session.sessionCode, newName);
    } else {
      emit('rename-cancel');
    }
  };

  const handleRenameCancel = () => {
    emit('rename-cancel');
  };

  // bk-input 的 keyup 事件签名为 (value: string, event: KeyboardEvent)
  // 不能直接使用 @keyup.enter 修饰符，需手动检查 event.key
  const handleKeyup = (_value: string, event: KeyboardEvent) => {
    if (event.key === 'Enter') {
      handleRenameConfirm();
    } else if (event.key === 'Escape') {
      handleRenameCancel();
    }
  };
</script>

<style lang="scss" scoped>
  .history-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    height: 28px;
    color: #4d4f56;
    padding: 0 8px;
    border-radius: 2px;
    cursor: pointer;

    .history-item-actions {
      color: #979ba5;
      display: flex;
      align-items: center;
      gap: 4px;
      opacity: 0;
      transition: opacity 0.1s ease;

      .bkai-icon {
        font-size: 14px;
      }
    }

    &:hover {
      background: #f0f1f5;

      .history-item-actions {
        opacity: 1;
      }
    }

    &.active {
      background: #e1ecff;
      color: #3a84ff;
      font-weight: 700;
    }
  }
</style>
