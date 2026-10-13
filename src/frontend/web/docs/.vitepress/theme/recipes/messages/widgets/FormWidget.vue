<template>
  <div class="fw">
    <div class="fw__title">{{ data.title ?? '请确认' }}</div>
    <div
      v-for="field in fields"
      :key="field.label"
      class="fw__field"
    >
      <span class="fw__label">{{ field.label }}</span>
      <select
        v-if="field.type === 'select'"
        v-model="values[field.label]"
        :disabled="!!submitted"
        class="fw__control"
      >
        <option
          v-for="option in field.options ?? []"
          :key="option"
          :value="option"
        >
          {{ option }}
        </option>
      </select>
      <input
        v-else
        v-model="values[field.label]"
        :disabled="!!submitted"
        class="fw__control"
        :placeholder="field.placeholder"
      >
    </div>
    <div class="fw__actions">
      <button
        v-for="(action, index) in actions"
        :key="action"
        type="button"
        class="fw__btn"
        :class="{ 'is-primary': index === 0 }"
        :disabled="!!submitted"
        @click="submit(action)"
      >
        {{ action }}
      </button>
      <span
        v-if="submitted"
        class="fw__done"
      >已选择「{{ submitted }}」</span>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, reactive, ref } from 'vue';

  import type { FormSubmit } from './types';

  /** 自定义块 JSON：{ type: 'form', title, fields: [{ label, type, options?, placeholder? }], actions } */
  interface FormField {
    label: string;
    type?: 'select' | 'text';
    options?: string[];
    placeholder?: string;
  }

  interface FormData {
    title?: string;
    fields?: FormField[];
    actions?: string[];
  }

  const props = defineProps<{ data: FormData }>();
  const emit = defineEmits<{ submit: [payload: FormSubmit] }>();

  const fields = computed(() => props.data.fields ?? []);
  const actions = computed(() => props.data.actions ?? ['确认']);
  const values = reactive<Record<string, string>>(
    Object.fromEntries(fields.value.map(f => [f.label, f.type === 'select' ? (f.options?.[0] ?? '') : ''])),
  );
  const submitted = ref('');

  const submit = (action: string) => {
    submitted.value = action;
    emit('submit', { title: props.data.title ?? '', action, values: { ...values } });
  };
</script>

<style scoped>
  .fw {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 360px;
    padding: 12px;
    background: #fafbfd;
    border: 1px solid #eaebf0;
    border-radius: 6px;
  }

  .fw__title {
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .fw__field {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
  }

  .fw__label {
    flex: 0 0 80px;
    color: #63656e;
  }

  .fw__control {
    flex: 1;
    height: 28px;
    padding: 0 8px;
    font-size: 12px;
    background: #fff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
  }

  .fw__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .fw__btn {
    height: 28px;
    padding: 0 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
  }

  .fw__btn.is-primary {
    color: #fff;
    background: #3a84ff;
    border-color: #3a84ff;
  }

  .fw__btn:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .fw__done {
    font-size: 12px;
    color: #1a9f45;
  }
</style>
