<template>
  <table class="ai-simple-table">
    <thead>
      <tr>
        <th
          v-for="col in columns"
          :key="col.key"
        >
          {{ col.label }}
        </th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="(row, index) in data"
        :key="index"
      >
        <td
          v-for="col in columns"
          :key="col.key"
          :class="{ 'is-break-all': col.breakAll }"
        >
          {{ row[col.key] ?? '--' }}
        </td>
      </tr>
      <tr v-if="!data.length">
        <td
          class="is-empty"
          :colspan="columns.length"
        >
          --
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script setup lang="ts">
  export interface SimpleTableColumn {
    breakAll?: boolean;
    key: string;
    label: string;
  }

  defineProps<{
    columns: SimpleTableColumn[];
    data: Record<string, unknown>[];
  }>();
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-simple-table {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid variables.$color-border;

    th,
    td {
      padding: 11px 16px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      text-align: left;
      border-bottom: 1px solid variables.$color-border;
    }

    th {
      font-weight: normal;
      color: variables.$color-title;
      background: variables.$color-bg-light;
    }

    td {
      color: variables.$color-text;
      background: white;
    }

    tr:last-child td {
      border-bottom: none;
    }

    .is-break-all {
      word-break: break-all;
    }

    .is-empty {
      color: variables.$color-text-secondary;
      text-align: center;
    }
  }
</style>
