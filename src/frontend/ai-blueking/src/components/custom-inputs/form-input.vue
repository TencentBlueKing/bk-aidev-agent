<template>
  <bk-input
    :model-value="value"
    class="bk-ai-custom-input"
    :placeholder="props.placeholder"
    :disabled="props.disabled"
    :resize="false"
    :rows="props.rows || 3"
    @update:modelValue="updateValue"
  />
</template>

<script setup lang="ts">
  import { Input as BkInput } from 'bkui-vue';
  import { computed } from 'vue';

  const props = defineProps<{
    modelValue: string;
    placeholder?: string;
    disabled?: boolean;
    rows?: number;
  }>();

  const emit = defineEmits(['update:modelValue']);

  const value = computed(() => props.modelValue);

  const updateValue = (val: string) => {
    emit('update:modelValue', val);
  };
</script>
<style lang="scss" scoped>
.bk-ai-custom-input :deep(textarea) {
  background-color: #fff;
}
</style>