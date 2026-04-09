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
  .ai-simple-table {
    $color-title: #313238;
    $color-text: #4d4f56;
    $color-text-secondary: #979ba5;
    $color-border: #dcdee5;
    $color-bg-light: #fafbfd;

    width: 100%;
    border-collapse: collapse;
    border: 1px solid $color-border;

    th,
    td {
      padding: 11px 16px;
      font-size: 12px;
      line-height: 20px;
      text-align: left;
      border-bottom: 1px solid $color-border;
    }

    th {
      font-weight: normal;
      color: $color-title;
      background: $color-bg-light;
    }

    td {
      color: $color-text;
      background: white;
    }

    tr:last-child td {
      border-bottom: none;
    }

    .is-break-all {
      word-break: break-all;
    }

    .is-empty {
      color: $color-text-secondary;
      text-align: center;
    }
  }
</style>
