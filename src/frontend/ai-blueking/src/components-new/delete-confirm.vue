<template>
  <div class="delete-confirm-wrapper">
    <div class="delete-confirm-title">{{ title }}</div>
    <div class="delete-confirm-content">{{ content }}</div>
    <div class="delete-confirm-footer">
      <BkButton
        style="width: 64px; min-width: 64px"
        size="small"
        theme="danger"
        @click="handleConfirm"
        >{{ t('删除') }}</BkButton
      >
      <BkButton
        style="width: 64px; min-width: 64px"
        size="small"
        theme="default"
        @click="handleCancel"
        >{{ t('取消') }}</BkButton
      >
    </div>
  </div>
</template>

<script setup lang="ts">
  import { Button as BkButton } from 'bkui-vue';

  import { t } from '../lang';
  const props = defineProps<{
    onConfirm: () => void;
    onCancel: () => void;
    title?: string;
    content?: string;
  }>();

  // 提供默认值
  const title = props.title || '确认删除该提问？';
  const content = props.content || '删除操作无法撤回，请谨慎操作！';

  // 事件处理
  const handleCancel = () => {
    props.onCancel();
  };

  const handleConfirm = () => {
    props.onConfirm();
  };
</script>

<style lang="scss" scoped>
  .delete-confirm-wrapper {
    min-width: 248px;
    padding: 16px;
    color: #63656e;
    text-align: left;
    background-color: #fff;

    .delete-confirm-title {
      font-size: 16px;
      font-weight: 700;
      line-height: 24px;
      color: #313238;
    }

    .delete-confirm-content {
      margin: 8px 0 16px;
      font-size: 12px;
      line-height: 20px;
    }

    .delete-confirm-footer {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 16px;
    }
  }
</style>

<style>
  .tippy-box[data-theme~='white'] {
    color: #313238;
    background-color: white;
    border-radius: 4px;
    box-shadow: 0 2px 6px 2px rgba(0, 0, 0, 0.15);
  }

  .tippy-box[data-theme~='white'] .tippy-arrow {
    color: white;
  }

  .tippy-box[data-theme~='white'] .tippy-content {
    padding: 0;
  }
</style>
