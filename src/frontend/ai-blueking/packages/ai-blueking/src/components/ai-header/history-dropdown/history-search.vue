<template>
  <div class="history-search">
    <bk-input
      :model-value="props.modelValue"
      behavior="simplicity"
      :placeholder="props.placeholder || t('搜索会话名称')"
      style="height: 22px"
      @update:model-value="handleInput"
    >
      <template #suffix>
        <span class="input-icon">
          <Search />
        </span>
      </template>
    </bk-input>
  </div>
</template>

<script setup lang="ts">
  import { Input as BkInput } from 'bkui-vue';
  import { Search } from 'bkui-vue/lib/icon';

  import { t } from '../../../lang';
  import type { HistorySearchProps, HistorySearchEmits } from './types';

  const props = withDefaults(defineProps<HistorySearchProps>(), {
    modelValue: '',
    placeholder: '',
  });

  const emit = defineEmits<HistorySearchEmits>();

  const handleInput = (value: string) => {
    emit('update:modelValue', value);
  };
</script>

<style lang="scss" scoped>
  .history-search {
    .input-icon {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
</style>
