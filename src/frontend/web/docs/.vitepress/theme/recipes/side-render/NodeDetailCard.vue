<template>
  <div class="ndc">
    <header class="ndc__head">
      <span class="ndc__title">{{ loading ? '加载中…' : nodeName || '节点详情' }}</span>
      <span class="ndc__tag">业务自定义详情</span>
      <!-- 由侧栏注入的「在对话中定位」按钮 -->
      <slot name="locateButton" />
    </header>
    <div
      v-if="loading"
      class="ndc__loading"
    >
      onCustomTabChange 拉取中…
    </div>
    <template v-else>
      <div
        v-if="errorText"
        class="ndc__error"
      >
        {{ errorText }}
      </div>
      <dl class="ndc__meta">
        <div><dt>流程</dt><dd>{{ data?.basic_info?.template_name ?? '—' }} / {{ data?.basic_info?.stage_name ?? '—' }}</dd></div>
        <div><dt>负责人</dt><dd>{{ data?.owner ?? '—' }}</dd></div>
        <div>
          <dt>处理手册</dt>
          <dd>
            <a
              v-if="data?.runbook"
              :href="data.runbook"
              rel="noreferrer"
              target="_blank"
            >{{ data.runbook }}</a>
            <span v-else>—</span>
          </dd>
        </div>
      </dl>
      <div class="ndc__section">输入</div>
      <table class="ndc__table">
        <tr
          v-for="(value, key) in data?.inputs ?? {}"
          :key="key"
        >
          <th>{{ key }}</th>
          <td>{{ typeof value === 'object' ? JSON.stringify(value) : value }}</td>
        </tr>
      </table>
      <div class="ndc__section">输出</div>
      <table class="ndc__table">
        <tr
          v-for="output in data?.outputs ?? []"
          :key="output.key"
        >
          <th>{{ output.key }}</th>
          <td>{{ String(output.value) }}</td>
        </tr>
      </table>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  /** task_node_info 的返回 + onCustomTabChange 补充的业务字段 */
  interface NodeDetail {
    basic_info?: { template_name?: string; stage_name?: string };
    inputs?: Record<string, unknown>;
    outputs?: { key: string; value: unknown }[];
    owner?: string;
    runbook?: string;
  }

  defineOptions({ inheritAttrs: false });

  const props = defineProps<{ loading?: boolean; nodeName?: string; data?: NodeDetail }>();

  const errorText = computed(() => {
    const ex = props.data?.outputs?.find(o => o.key === 'ex_data')?.value;
    return ex ? String(ex) : '';
  });
</script>

<style scoped>
  .ndc {
    padding: 12px 14px;
    font-size: 12px;
    color: #313238;
  }

  .ndc__head {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 10px;
  }

  .ndc__title {
    font-size: 14px;
    font-weight: 600;
  }

  .ndc__tag {
    padding: 0 6px;
    margin-right: auto;
    font-size: 11px;
    color: #7c3aed;
    background: #efe7ff;
    border-radius: 2px;
  }

  .ndc__loading {
    padding: 20px 0;
    color: #979ba5;
  }

  .ndc__error {
    padding: 8px 10px;
    margin-bottom: 10px;
    color: #ea3636;
    background: #ffeded;
    border-radius: 2px;
  }

  .ndc__meta {
    display: grid;
    gap: 4px;
    margin: 0 0 10px;
  }

  .ndc__meta div {
    display: flex;
    gap: 8px;
  }

  .ndc__meta dt {
    flex: 0 0 56px;
    color: #979ba5;
  }

  .ndc__meta dd {
    margin: 0;
    word-break: break-all;
  }

  .ndc__section {
    margin: 10px 0 4px;
    font-weight: 600;
    color: #63656e;
  }

  .ndc__table {
    width: 100%;
    border-collapse: collapse;
  }

  .ndc__table th,
  .ndc__table td {
    padding: 4px 6px;
    text-align: left;
    vertical-align: top;
    border: 1px solid #f0f1f5;
  }

  .ndc__table th {
    width: 96px;
    font-family: var(--vp-font-family-mono);
    font-weight: 400;
    color: #63656e;
    background: #fafbfd;
  }

  .ndc__table td {
    font-family: var(--vp-font-family-mono);
    word-break: break-all;
  }
</style>
