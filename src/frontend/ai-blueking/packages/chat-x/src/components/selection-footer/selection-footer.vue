<!--
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
-->
<template>
  <div class="ai-selection-footer">
    <div class="ai-selection-footer-left">
      <Checkbox
        :model-value="isAllSelected"
        @update:model-value="(checked: boolean) => emit('toggle-all', checked)"
      />
      <span class="select-all-text">{{ t('全选') }}</span>
    </div>
    <div class="ai-selection-footer-right">
      <Button
        :disabled="loading"
        @click="emit('cancel')"
      >
        {{ t('取消') }}
      </Button>
      <Button
        :disabled="selectedCount === 0"
        :loading="loading"
        theme="primary"
        @click="emit('confirm')"
      >
        {{ t('确定') }}
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { Button, Checkbox } from 'bkui-vue';

  import { t } from '../../lang/lang';

  defineProps<{
    /** 是否全选 */
    isAllSelected: boolean;
    /** 是否加载中 */
    loading?: boolean;
    /** 已选数量 */
    selectedCount: number;
  }>();

  const emit = defineEmits<{
    /** 取消选择 */
    (e: 'cancel'): void;
    /** 确认选择 */
    (e: 'confirm'): void;
    /** 切换全选状态 */
    (e: 'toggle-all', checked: boolean): void;
  }>();
</script>

<style lang="scss">
  .ai-selection-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 8px 0;
    border-top: 1px solid #dcdee5;

    &-left {
      display: flex;
      gap: 8px;
      align-items: center;

      .select-all-text {
        font-size: var(--ai-font-size, 12px);
        color: #63656e;
      }
    }

    &-right {
      display: flex;
      gap: 8px;
      align-items: center;
    }
  }
</style>
