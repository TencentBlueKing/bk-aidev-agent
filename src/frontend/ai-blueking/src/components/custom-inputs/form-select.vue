<template>
  <bk-select
    v-model="value"
    :popoverOptions="{
      boundary: 'parent',
    }"
    :placeholder="props.placeholder"
    :disabled="props.disabled"
  >
    <bk-option
      v-for="option in props.options"
      :id="option.value"
      :key="option.value"
      :name="option.label"
    >
      {{ option.label }}
    </bk-option>
  </bk-select>
</template>

<script setup lang="ts">
  import BkSelect from 'bkui-vue/lib/select';
  import { BkOption } from 'bkui-vue/lib/select';
  import { computed } from 'vue';

  const props = defineProps<{
    modelValue: any;
    options: Array<{ label: string; value: any }>;
    placeholder?: string;
    disabled?: boolean;
  }>();

  const emit = defineEmits(['update:modelValue']);

  const value = computed({
    get() {
      return props.modelValue;
    },
    set(val) {
      emit('update:modelValue', val);
    },
  });
</script>
